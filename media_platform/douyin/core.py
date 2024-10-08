import asyncio
import itertools
import os
import random
from asyncio import Task
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import (BrowserContext, BrowserType, Page,
                                  async_playwright)

import config
from base.base import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import douyin as douyin_store
from tools import utils
from var import crawler_type_var

from .client import DOUYINClient
from .exception import DataFetchError
from .field import PublishTimeType
from .login import DouYinLogin


class DouYinCrawler(AbstractCrawler):
    platform: str
    login_type: str
    crawler_type: str
    context_page: Page
    dy_client: DOUYINClient
    browser_context: BrowserContext

    def __init__(self) -> None:
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"  # fixed
        self.index_url = "https://www.douyin.com"

    def init_config(self, platform: str, login_type: str, crawler_type: str) -> None:
        self.platform = platform
        self.login_type = login_type
        self.crawler_type = crawler_type

    async def start(self) -> None:
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
            await self.context_page.goto(self.index_url)

            self.dy_client = await self.create_douyin_client(httpx_proxy_format)
            if not await self.dy_client.pong(browser_context=self.browser_context):
                if self.crawler_type == "login":
                    login_obj = DouYinLogin(
                        login_type=self.login_type,
                        login_phone="",  # you phone number
                        browser_context=self.browser_context,
                        context_page=self.context_page,
                        cookie_str=os.environ.get("COOKIES", config.COOKIES)
                    )
                    await login_obj.begin()
                    await self.dy_client.update_cookies(browser_context=self.browser_context)
                    return
                else:
                    utils.logger.error("[DouyinCrawler.start] Douyin Crawler login has expired ...")
                    return {"code" : 1, "msg" : "Douyin Crawler login has expired, please update account state..."}

            crawler_type_var.set(self.crawler_type)
            if self.crawler_type == "search":
                await self.search()
            elif self.crawler_type == "detail":
                await self.get_specified_awemes()

            utils.logger.info("[DouYinCrawler.start] Douyin Crawler finished ...")

    async def search(self) -> None:
        utils.logger.info("[DouYinCrawler.search] Begin search douyin keywords")
        dy_limit_count = 10  # douyin limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < dy_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = dy_limit_count

        resource_name_list = os.environ.get("RESOURCE_NAME","").split(",")
        keywords_list = os.environ.get("KEYWORDS",config.KEYWORDS).split(",")
        combined_list = [f"{resource}{keyword}" for resource, keyword in itertools.product(resource_name_list, keywords_list)]
        search_keyword = ",".join(combined_list)
        for keyword in search_keyword.split(","):
            utils.logger.info(f"[DouYinCrawler.search] Current keyword: {keyword}")
            page = 0
            while (page + 1) * dy_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                aweme_list: List[str] = []
                try:
                    posts_res = await self.dy_client.search_info_by_keyword(keyword=keyword,
                                                                            offset=page * dy_limit_count,
                                                                            publish_time=PublishTimeType.UNLIMITED
                                                                            )
                    utils.logger.error(f"[DouYinCrawler.search] search douyin keyword: {keyword} successfully")
                except DataFetchError:
                    utils.logger.error(f"[DouYinCrawler.search] search douyin keyword: {keyword} failed")
                    break
                page += 1
                for post_item in posts_res.get("data"):
                    try:
                        aweme_info: Dict = post_item.get("aweme_info") or \
                                           post_item.get("aweme_mix_info", {}).get("mix_items")[0]
                    except TypeError:
                        continue
                    aweme_list.append(aweme_info.get("aweme_id", ""))
                    await douyin_store.update_douyin_aweme(aweme_item=aweme_info)

                # 获取视频截图取证
                if config.ENABLE_FORENSICS:
                    semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
                    task_list = [
                        self.get_aweme_forensics(aweme_id=aweme_id, semaphore=semaphore)
                        for aweme_id in aweme_list
                    ]

                    await asyncio.gather(*task_list)

                utils.logger.info(f"[DouYinCrawler.search] keyword:{keyword}, aweme_list:{aweme_list}")
                await self.batch_get_note_comments(aweme_list)

    async def get_specified_awemes(self):
        """
        Get the information and comments of the specified aweme
        """
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = [
            self.get_aweme_detail(aweme_id=aweme_id, semaphore=semaphore) for aweme_id in config.DY_SPECIFIED_ID_LIST
        ]
        aweme_details = await asyncio.gather(*task_list)
        for aweme_detail in aweme_details:
            if aweme_detail is not None:
                await douyin_store.update_douyin_aweme(aweme_detail)
        await self.batch_get_note_comments(config.DY_SPECIFIED_ID_LIST)

    async def get_aweme_forensics(self, aweme_id: str, semaphore: asyncio.Semaphore) -> None:
        """
        Get note forensics
        """
        async with semaphore:
            try:
                await self.dy_client.forensics_by_id(aweme_id=aweme_id, context_page= await self.browser_context.new_page())
            except KeyError as ex:
                utils.logger.error(
                    f"[DouYinCrawler.get_aweme_detail] have not fund note detail aweme_id:{aweme_id}, err: {ex}")

    async def get_aweme_detail(self, aweme_id: str, semaphore: asyncio.Semaphore) -> Any:
        """
        Get note detail
        :param aweme_id: str
        :param semaphore: asyncio.S
        :return:
        """
        async with semaphore:
            try:
                await self.dy_client.forensics_by_id(aweme_id=aweme_id)
                return await self.dy_client.get_video_by_id(aweme_id)
            except DataFetchError as ex:
                utils.logger.error(f"[DouYinCrawler.get_aweme_detail] Get aweme detail error: {ex}")
                return None
            except KeyError as ex:
                utils.logger.error(f"[DouYinCrawler.get_aweme_detail] have not fund note detail aweme_id:{aweme_id}, err: {ex}")
                return None

    async def batch_get_note_comments(self, aweme_list: List[str]) -> None:
        """
        Batch get note comments
        :param aweme_list: List[str]
        :return:
        """
        if not int(os.environ.get("ENABLE_GET_COMMENTS", config.ENABLE_GET_COMMENTS)):
            utils.logger.info(f"[DouYinCrawler.batch_get_note_comments] Crawling comment mode is not enabled")
            return

        task_list: List[Task] = []
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        for aweme_id in aweme_list:
            task = asyncio.create_task(
                self.get_comments(aweme_id, semaphore), name=aweme_id)
            task_list.append(task)
        if len(task_list) > 0 :
            await asyncio.wait(task_list)

    async def get_comments(self, aweme_id: str, semaphore: asyncio.Semaphore) -> None:
        """
        Get aweme comments
        :param aweme_id: str
        :param semaphore: asyncio.S
        :return:
        """
        async with semaphore:
            try:
                # 将关键词列表传递给 get_aweme_all_comments 方法
                await self.dy_client.get_aweme_all_comments(
                    aweme_id=aweme_id,
                    crawl_interval=random.random(),
                    callback=douyin_store.batch_update_dy_aweme_comments

                )
                utils.logger.info(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} comments have all been obtained and filtered ...")
            except DataFetchError as e:
                utils.logger.error(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} get comments failed, error: {e}")

    @staticmethod
    def format_proxy_info(ip_proxy_info: IpInfoModel) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        format proxy info for playwright and httpx
        :param ip_proxy_info: IpInfoModel
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

    async def create_douyin_client(self, httpx_proxy: Optional[str]) -> DOUYINClient:
        """
        Create douyin client
        :param httpx_proxy: Optional[str]
        :return:
        """
        cookie_str, cookie_dict = utils.convert_cookies(await self.browser_context.cookies())  # type: ignore
        douyin_client = DOUYINClient(
            proxies=httpx_proxy,
            headers={
                "User-Agent": self.user_agent,
                "Cookie": cookie_str,
                "Host": "www.douyin.com",
                "Origin": "https://www.douyin.com/",
                "Referer": "https://www.douyin.com/",
                "Content-Type": "application/json;charset=UTF-8"
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
        return douyin_client

    async def launch_browser(
            self,
            chromium: BrowserType,
            playwright_proxy: Optional[Dict],
            user_agent: Optional[str],
            headless: bool = True
    ) -> BrowserContext:
        """
        Launch browser and create browser context
        :param chromium: BrowserType
        :param playwright_proxy: Optional[Dict]
        :param user_agent: Optional[str]
        :param headless: bool
        :return:
        """
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
            )  # type: ignore
            return browser_context
        else:
            browser = await chromium.launch(channel="msedge", headless=headless, proxy=playwright_proxy)  # type: ignore
            browser_context = await browser.new_context(
                viewport={"width": 2600, "height": 1080},
                user_agent=user_agent
            )
            return browser_context

    async def close(self) -> None:
        """Close browser context"""
        await self.browser_context.close()
        utils.logger.info("[DouYinCrawler.close] Browser context closed ...")
