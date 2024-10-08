import asyncio
import itertools
import os
import random
import time
from asyncio import Task
from typing import Dict, List, Optional, Tuple

from playwright.async_api import (BrowserContext, BrowserType, Page,
                                  async_playwright)

import config
from base.base import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import kuaishou as kuaishou_store
from tools import utils
from var import comment_tasks_var, crawler_type_var

from .client import KuaiShouClient
from .exception import DataFetchError
from .login import KuaishouLogin


class KuaishouCrawler(AbstractCrawler):
    platform: str
    login_type: str
    crawler_type: str
    context_page: Page
    ks_client: KuaiShouClient
    browser_context: BrowserContext

    def __init__(self):
        self.index_url = "https://www.kuaishou.com"
        self.user_agent = utils.get_user_agent()

    def init_config(self, platform: str, login_type: str, crawler_type: str):
        self.platform = platform
        self.login_type = login_type
        self.crawler_type = crawler_type

    async def start(self):
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = self.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # Launch a browser context.
            chromium = playwright.chromium
            self.browser_context = await self.launch_browser(
                chromium,
                None,
                self.user_agent,
                headless=config.HEADLESS
            )
            # stealth.min.js is a js script to prevent the website from detecting the crawler.
            await self.browser_context.add_init_script(path="libs/stealth.min.js")
            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(f"{self.index_url}?isHome=1")

            # Create a client to interact with the kuaishou website.
            self.ks_client = await self.create_ks_client(httpx_proxy_format)
            if not await self.ks_client.pong():
                if self.crawler_type == "login":
                    login_obj = KuaishouLogin(
                        login_type=self.login_type,
                        login_phone=httpx_proxy_format,
                        browser_context=self.browser_context,
                        context_page=self.context_page,
                        cookie_str=os.environ.get("COOKIES", config.COOKIES)
                    )
                    await login_obj.begin()
                    await self.ks_client.update_cookies(browser_context=self.browser_context)
                else:
                    utils.logger.error("[KuaishouCrawler.start] Kuaishou Crawler login has expired ...")
                    return {"code": 1, "msg": "Kuaishou Crawler login has expired, please update account state..."}

            crawler_type_var.set(self.crawler_type)
            if self.crawler_type == "search":
                await self.search()
            elif self.crawler_type == "detail":
                await self.get_specified_videos()
            elif self.crawler_type == "report":
                await self.report_specified_video()
            else:
                pass

            utils.logger.info("[KuaishouCrawler.start] Kuaishou Crawler finished ...")

    async def search(self):
        utils.logger.info("[KuaishouCrawler.search] Begin search kuaishou keywords")
        ks_limit_count = 20  # kuaishou limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < ks_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = ks_limit_count

        resource_name_list = os.environ.get("RESOURCE_NAME", "").split(",")
        keywords_list = os.environ.get("KEYWORDS", config.KEYWORDS).split(",")
        combined_list = [f"{resource}{keyword}" for resource, keyword in
                         itertools.product(resource_name_list, keywords_list)]
        search_keyword = ",".join(combined_list)
        for keyword in search_keyword.split(","):
            utils.logger.info(f"[KuaishouCrawler.search] Current search keyword: {keyword}")
            page = 1
            while page * ks_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                video_id_list: List[str] = []
                videos_res = await self.ks_client.search_info_by_keyword(
                    keyword=keyword,
                    pcursor=str(page),
                )
                if not videos_res:
                    utils.logger.error(f"[KuaishouCrawler.search] search info by keyword:{keyword} not found data")
                    continue

                vision_search_photo: Dict = videos_res.get("visionSearchPhoto")
                if vision_search_photo.get("result") != 1:
                    utils.logger.error(f"[KuaishouCrawler.search] search info by keyword:{keyword} not found data ")
                    continue

                # for video_detail in vision_search_photo.get("feeds"):
                #     video_id_list.append(video_detail.get("photo", {}).get("id"))
                #     await kuaishou_store.update_kuaishou_video(video_item=video_detail)

                semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
                task_list = [
                    self.get_video_info_task(video_id=video_detail.get("photo", {}).get("id"), semaphore=semaphore)
                    for video_detail in vision_search_photo.get("feeds")
                ]
                video_details = await asyncio.gather(*task_list)

                for video_detail in video_details:
                    if video_detail is not None:
                        video_id_list.append(video_detail.get("photo", {}).get("id"))
                        await kuaishou_store.update_kuaishou_video(video_detail)

                video_detail = {
                    "id": "3xips9fbqjx66iq",
                    "user_id": "3xt5dxdya79nggu"
                }

                if config.ENABLE_REPORT:
                    result = await self.ks_client.report_by_id(video_id=video_detail.get("id"), reportUserID=video_detail.get("user_id"), reason="侵犯版权，涉嫌传播盗版资源内容")
                    print("kuaishou report result:", result)

                # batch fetch video comments
                page += 1

                utils.logger.info(f"[KuaiShouCrawler.search] keyword:{keyword}, video_list:{video_id_list}")
                await self.batch_get_video_comments(video_id_list)

    async def report_specified_video(self, video_list : Dict[str, str] = None) -> None:
        """
        Report the specified post
        :param video_list:
        :return:
        """
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = [
            self.report_video_task(video_id=video_detail.get("id"), reportUserId=video_detail.get("user_id"), semaphore=semaphore)
            for video_detail in video_list
        ]
        await asyncio.gather(*task_list)

    async def report_video_task(self, video_id: str, reportUserId: str, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """
        Report video task
        :param video_id:
        :param reportUserId:
        :param semaphore:
        :return:
        """
        async with semaphore:
            try:
                reason = "侵犯版权，涉嫌传播盗版资源内容"
                result = await self.ks_client.report_by_id(video_id=video_id, reportUserID=reportUserId, reason=reason)
                return result
            except KeyError as ex:
                utils.logger.error(f"[KuaishouCrawler.report_video_task] have not fund note detail video_id:{video_id}, err: {ex}")
                return None


    async def get_specified_videos(self):
        """
        Get the information and comments of the specified video
        """
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = [
            self.get_video_info_task(video_id=video_id, semaphore=semaphore) for video_id in config.KS_SPECIFIED_ID_LIST
        ]
        video_details = await asyncio.gather(*task_list)
        for video_detail in video_details:
            if video_detail is not None:
                await kuaishou_store.update_kuaishou_video(video_detail)
        await self.batch_get_video_comments(config.KS_SPECIFIED_ID_LIST)

    async def get_video_info_task(self, video_id: str, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """
        Get video detail task
        :param video_id:
        :param semaphore:
        :return:
        """
        async with semaphore:
            try:
                if config.ENABLE_FORENSICS:
                    await self.ks_client.forensics_by_id(video_id=video_id,
                                                         context_page=await self.browser_context.new_page())
                result = await self.ks_client.get_video_info(video_id)
                return result.get("visionVideoDetail")
            except DataFetchError as ex:
                utils.logger.error(f"[KuaishouCrawler.get_video_info_task] Get video detail error: {ex}")
                return None
            except KeyError as ex:
                utils.logger.error(f"[KuaishouCrawler.get_video_info_task] have not fund note detail video_id:{video_id}, err: {ex}")
                return None

    async def batch_get_video_comments(self, video_id_list: List[str]):
        """
        batch get video comments
        :param video_id_list:
        :return:
        """
        if not int(os.environ.get("ENABLE_GET_COMMENTS", config.ENABLE_GET_COMMENTS)):
            utils.logger.info(f"[KuaishouCrawler.batch_get_note_comments] Crawling comment mode is not enabled")
            return

        utils.logger.info(f"[KuaishouCrawler.batch_get_video_comments] video ids:{video_id_list}")
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list: List[Task] = []
        for video_id in video_id_list:
            task = asyncio.create_task(self.get_comments(video_id, semaphore), name=video_id)
            task_list.append(task)

        comment_tasks_var.set(task_list)
        await asyncio.gather(*task_list)

    async def get_comments(self, video_id: str, semaphore: asyncio.Semaphore):
        """
        get comment for video id
        :param video_id:
        :param semaphore:
        :return:
        """
        async with semaphore:
            try:
                utils.logger.info(f"[KuaishouCrawler.get_comments] begin get video_id: {video_id} comments ...")
                await self.ks_client.get_video_all_comments(
                    photo_id=video_id,
                    crawl_interval=random.random(),
                    callback=kuaishou_store.batch_update_ks_video_comments
                )
            except DataFetchError as ex:
                utils.logger.error(f"[KuaishouCrawler.get_comments] get video_id: {video_id} comment error: {ex}")
            except Exception as e:
                utils.logger.error(f"[KuaishouCrawler.get_comments] may be been blocked, err:{e}")
                # use time.sleeep block main coroutine instead of asyncio.sleep and cacel running comment task
                # maybe kuaishou block our request, we will take a nap and update the cookie again
                current_running_tasks = comment_tasks_var.get()
                for task in current_running_tasks:
                    task.cancel()
                time.sleep(20)
                await self.context_page.goto(f"{self.index_url}?isHome=1")
                await self.ks_client.update_cookies(browser_context=self.browser_context)

    @staticmethod
    def format_proxy_info(ip_proxy_info: IpInfoModel) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        format proxy info for playwright and httpx
        :param ip_proxy_info:
        :return:
        """
        playwright_proxy = {
            "server": f"{ip_proxy_info.protocol}{ip_proxy_info.ip}:{ip_proxy_info.port}",
            "username": ip_proxy_info.user,
            "password": ip_proxy_info.password,
        }
        httpx_proxy = {
            f"{ip_proxy_info.protocol}": f"http://{ip_proxy_info.user}:{ip_proxy_info.password}@{ip_proxy_info.ip}:{ip_proxy_info.port}"
        }
        return playwright_proxy, httpx_proxy

    async def create_ks_client(self, httpx_proxy: Optional[str]) -> KuaiShouClient:
        """
        Create xhs client
        :param httpx_proxy:
        :return:
        """
        utils.logger.info("[KuaishouCrawler.create_ks_client] Begin create kuaishou API client ...")
        cookie_str, cookie_dict = utils.convert_cookies(await self.browser_context.cookies())
        xhs_client_obj = KuaiShouClient(
            proxies=httpx_proxy,
            headers={
                "User-Agent": self.user_agent,
                "Cookie": cookie_str,
                "Origin": self.index_url,
                "Referer": self.index_url,
                "Content-Type": "application/json;charset=UTF-8"
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
        return xhs_client_obj

    async def launch_browser(
            self,
            chromium: BrowserType,
            playwright_proxy: Optional[Dict],
            user_agent: Optional[str],
            headless: bool = True
    ) -> BrowserContext:
        """
        Launch browser and create browser context
        :param chromium:
        :param playwright_proxy:
        :param user_agent:
        :param headless:
        :return:
        """
        utils.logger.info("[KuaishouCrawler.launch_browser] Begin create browser context ...")
        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(os.getcwd(), "browser_data",
                                         config.USER_DATA_DIR % self.platform)  # type: ignore
            browser_context = await chromium.launch_persistent_context(
                channel="msedge",
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,  # type: ignore
                viewport={"width": 2600, "height": 1080},
                user_agent=user_agent
            )
            return browser_context
        else:
            browser = await chromium.launch(channel="msedge", headless=headless, proxy=playwright_proxy)  # type: ignore
            browser_context = await browser.new_context(
                viewport={"width": 2600, "height": 1080},
                user_agent=user_agent
            )
            return browser_context

    async def close(self):
        """
        Close browser context
        """
        await self.browser_context.close()
        utils.logger.info("[KuaishouCrawler.close] Browser context closed ...")
