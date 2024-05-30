
import asyncio
import copy
import urllib.parse
from typing import Any, Callable, Dict, Optional, Union

import execjs
import httpx
from playwright.async_api import BrowserContext, Page, TimeoutError

from base.base import AbstactApiClient
from tools import utils
from var import request_keyword_var
from .exception import *
from .field import *


class DOUYINClient(AbstactApiClient):
    def __init__(
            self,
            timeout=30,
            proxies=None,
            *,
            headers: Dict,
            playwright_page: Optional[Page],
            cookie_dict: Dict
    ):
        self.proxies = proxies
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.douyin.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict

    async def __process_req_params(self, params: Optional[Dict] = None, headers: Optional[Dict] = None):
        if not params:
            return
        headers = headers or self.headers
        local_storage: Dict = await self.playwright_page.evaluate("() => window.localStorage")  # type: ignore
        douyin_js_obj = execjs.compile(open('libs/douyin.js').read())
        common_params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "cookie_enabled": "true",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Edge",
            "browser_version": "124.0.0.0", # 110.0
            "browser_online": "true",
            "engine_name": "Blink", #Gecko
            "os_name": "Windows",
            "os_version": "10",
            "engine_version": "124.0.0.0", #109.0
            "platform": "PC",
            "screen_width": "1920",
            "screen_height": "1200",
            # " webid": douyin_js_obj.call("get_web_id"),
            # "msToken": local_storage.get("xmst"),
            # "msToken": "abL8SeUTPa9-EToD8qfC7toScSADxpg6yLh2dbNcpWHzE0bT04txM_4UwquIcRvkRb9IU8sifwgM1Kwf1Lsld81o9Irt2_yNyUbbQPSUO8EfVlZJ_78FckDFnwVBVUVK",
        }
        params.update(common_params)
        query = '&'.join([f'{k}={v}' for k, v in params.items()])
        x_bogus = douyin_js_obj.call('sign', query, headers["User-Agent"])
        params["X-Bogus"] = x_bogus
        # print(x_bogus, query)

    async def request(self, method, url, **kwargs):
        async with httpx.AsyncClient(proxies=self.proxies) as client:
            response = await client.request(
                method, url, timeout=self.timeout,
                **kwargs
            )
            try:
                return response.json()
            except Exception as e:
                raise DataFetchError(f"{e}, {response.text}")

    async def get(self, uri: str, params: Optional[Dict] = None, headers: Optional[Dict] = None):
        await self.__process_req_params(params, headers)
        headers = headers or self.headers
        return await self.request(method="GET", url=f"{self._host}{uri}", params=params, headers=headers)

    async def post(self, uri: str, data: dict, headers: Optional[Dict] = None):
        await self.__process_req_params(data, headers)
        headers = headers or self.headers
        return await self.request(method="POST", url=f"{self._host}{uri}", data=data, headers=headers)

    async def pong(self, browser_context: BrowserContext) -> bool:
        """
        通过检测cookie中的__security_server_data_status字段来判断是否登录成功
        或者检测检测localStorage中的HasUserLogin字段
        Return:
        """
        utils.logger.info("[DOUYINClient.pong] Begin pong douyin...")
        local_storage = await self.playwright_page.evaluate("() => window.localStorage")
        if local_storage.get("HasUserLogin", "") == "1":
            return True
        _, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        return cookie_dict.get("__security_server_data_status") == "1"

    async def update_cookies(self, browser_context: BrowserContext):
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def search_info_by_keyword(
            self,
            keyword: str,
            offset: int = 0,
            search_channel: SearchChannelType = SearchChannelType.GENERAL,
            sort_type: SearchSortType = SearchSortType.GENERAL,
            publish_time: PublishTimeType = PublishTimeType.UNLIMITED
    ):
        """
        DouYin Web Search API
        :param keyword:
        :param offset:
        :param search_channel:
        :param sort_type:
        :param publish_time: ·
        :return:
        """
        params = {
            "keyword": urllib.parse.quote(keyword),
            "search_channel": search_channel.value,
            "sort_type": sort_type.value,
            "publish_time": publish_time.value,
            "search_source": "normal_search",
            "query_correct_type": "1",
            "is_filter_search": "0",
            "offset": offset,
            "count": 10  # must be set to 10
        }
        referer_url = "https://www.douyin.com/search/" + keyword
        referer_url += f"?publish_time={publish_time.value}&sort_type={sort_type.value}&type=general"
        headers = copy.copy(self.headers)
        headers["Referer"] = urllib.parse.quote(referer_url, safe=':/')
        return await self.get("/aweme/v1/web/general/search/single/", params, headers=headers)

    async def forensics_by_id(self, aweme_id: str, context_page: Page) -> Union[str, None]:
        """
        Force to get the video by aweme_id
        :param aweme_id:
        :param context_page:
        :return:
        """
        try:
            await context_page.goto(f"https://www.douyin.com/video/{aweme_id}")
            await asyncio.sleep(4)
            img_path = f"img_store/dy_fornesics_{aweme_id}.png"
            await context_page.screenshot(full_page=True, path=img_path, timeout=300000)
            await context_page.close()
            return img_path

        except TimeoutError as e:
            await context_page.close()
            utils.logger.error(f"[DOUYINClient.forensics_by_id] aweme {aweme_id} timeoutError {e}")
            return None


    async def get_video_by_id(self, aweme_id: str) -> Any:
        """
        DouYin Video Detail API
        :param aweme_id:
        :return:
        """
        params = {
            "aweme_id": aweme_id
        }
        headers = copy.copy(self.headers)
        # headers["Cookie"] = "s_v_web_id=verify_lol4a8dv_wpQ1QMyP_xemd_4wON_8Yzr_FJa8DN1vdY2m;"
        del headers["Origin"]
        res = await self.get("/aweme/v1/web/aweme/detail/", params, headers)
        return res.get("aweme_detail", {})

    async def get_aweme_comments(self, aweme_id: str, cursor: int = 0):
        """
        get note comments
        :param aweme_id:
        :param cursor:
        """
        uri = "/aweme/v1/web/comment/list/"
        params = {
            "aweme_id": aweme_id,
            "cursor": cursor,
            "count": 10,
            "item_type": 0
        }
        keywords = request_keyword_var.get()
        referer_url = "https://www.douyin.com/search/" + keywords + '?aid=3a3cec5a-9e27-4040-b6aa-ef548c2c1138&publish_time=0&sort_type=0&source=search_history&type=general'
        headers = copy.copy(self.headers)
        headers["Referer"] = urllib.parse.quote(referer_url, safe=':/')
        return await self.get(uri, params)

    async def get_aweme_all_comments(
            self,
            aweme_id: str,
            crawl_interval: float = 1.0,
            is_fetch_sub_comments=False,
            callback: Optional[Callable] = None,
    ):
        """
        获取帖子的所有评论，包括子评论
        :param aweme_id: 帖子ID
        :param crawl_interval: 抓取间隔
        :param is_fetch_sub_comments: 是否抓取子评论
        :param callback: 回调函数，用于处理抓取到的评论
        :return: 评论列表
        """
        result = []
        comments_has_more = 1
        comments_cursor = 0
        count = 0
        while comments_has_more and count< 2:
            comments_res = await self.get_aweme_comments(aweme_id, comments_cursor)
            comments_has_more = comments_res.get("has_more", 0)
            comments_cursor = comments_res.get("cursor", 0)
            comments = comments_res.get("comments", [])
            if not comments:
                continue
            result.extend(comments)
            if callback:  # 如果有回调函数，就执行回调函数
                await callback(aweme_id, comments)
            await asyncio.sleep(crawl_interval)
            count += 1
            if not is_fetch_sub_comments:
                continue
            # todo fetch sub comments
        return result