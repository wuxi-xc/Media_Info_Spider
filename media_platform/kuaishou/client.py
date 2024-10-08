# -*- coding: utf-8 -*-
import asyncio
import json
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

import httpx
import playwright.async_api
from playwright.async_api import BrowserContext, Page

from base.base import AbstactApiClient
from tools import utils
from .exception import DataFetchError
from .graphql import KuaiShouGraphQL


class KuaiShouClient(AbstactApiClient):
    def __init__(
            self,
            timeout=10,
            proxies=None,
            *,
            headers: Dict[str, str],
            playwright_page: Page,
            cookie_dict: Dict[str, str],
    ):
        self.proxies = proxies
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.kuaishou.com/graphql"
        self._domain = "https://www.kuaishou.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self.graphql = KuaiShouGraphQL()

    async def request(self, method, url, **kwargs) -> Any:
        async with httpx.AsyncClient(proxies=self.proxies) as client:
            response = await client.request(
                method, url, timeout=self.timeout,
                **kwargs
            )
        data: Dict = response.json()
        if data.get("errors"):
            raise DataFetchError(data.get("errors", "unkonw error"))
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None) -> Dict:
        final_uri = uri
        if isinstance(params, dict):
            final_uri = (f"{uri}?"
                         f"{urlencode(params)}")
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def post(self, uri: str, data: dict) -> Dict:
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return await self.request(method="POST", url=f"{self._host}{uri}",
                                  data=json_str, headers=self.headers)

    async def pong(self) -> bool:
        """
        通过发送请求查看请求状态来判断是否登录
        Return:
        """
        utils.logger.info("[KuaiShouClient.pong] Begin pong kuaishou...")
        ping_flag = False
        try:
            post_data = {
                "operationName": "visionProfileUserList",
                "variables": {
                    "ftype": 1,
                },
                "query": self.graphql.get("vision_profile")
            }
            res = await self.post("", post_data)
            if res.get("visionProfileUserList", {}).get("result") == 1:
                ping_flag = True
        except Exception as e:
            utils.logger.error(f"[KuaiShouClient.pong] Pong kuaishou failed: {e}, and try to login again...")
            ping_flag = False
        return ping_flag

    async def update_cookies(self, browser_context: BrowserContext):
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def search_info_by_keyword(self, keyword: str, pcursor: str):
        """
        KuaiShou web search api
        :param keyword: search keyword
        :param pcursor: limite page curson
        :return:
        """
        post_data = {
            "operationName": "visionSearchPhoto",
            "variables": {
                "keyword": keyword,
                "pcursor": pcursor,
                "page": "search"
            },
            "query": self.graphql.get("search_query")
        }
        return await self.post("", post_data)

    async def report_by_id(self, video_id: str, reason: str, reportUserID: str) -> bool:
        """
        举报视频
        Args:
            video_id: 视频ID
            reason: 举报原因
        Returns:
        """
        report_data = {
          "operationName": "ReportSubmitMutation",
          "variables": {
            "targetId": video_id,
            "reportType": 1,
            "page": "DETAIL",  #RECO_DETAIL
            "reportItem": 44,
            "reportDetail": reason,
            "reportedUserId": reportUserID,
            "extraPhotoId": ""
          },
          "query": self.graphql.get("report_content")
        }
        return await self.post("", report_data)


    async def forensics_by_id(self, video_id: str, context_page: Page) -> str:
        """
        进行视频截图取证
        Args:
            video_id: 视频ID
        Returns:
        """
        try:
            final_url = f'/short-video/{video_id}'

            await context_page.goto(f"{self._domain}{final_url}")

            await context_page.wait_for_load_state("load")
            await asyncio.sleep(3)

            img_path = f"img_store/ks_fornesics_{video_id}.png"
            await context_page.screenshot(full_page=True, path=img_path,timeout=90000)
            await context_page.close()
            return img_path

        except playwright.async_api.TimeoutError as e:
            await context_page.close()
            utils.logger.error(f"[KuaiShouClient.forensics_by_id] video {video_id} TimeoutError {e}")
            return ""


    async def get_video_info(self, photo_id: str) -> Dict:
        """
        Kuaishou web video detail api
        :param photo_id:
        :return:
        """
        post_data = {
            "operationName": "visionVideoDetail",
            "variables": {
                "photoId": photo_id,
                "page": "search"
            },
            "query": self.graphql.get("video_detail")
        }
        return await self.post("", post_data)

    async def get_video_comments(self, photo_id: str, pcursor: str = "") -> Dict:
        """get video comments
        :param photo_id: photo id you want to fetch
        :param pcursor: last you get pcursor, defaults to ""
        :return:
        """
        post_data = {
            "operationName": "commentListQuery",
            "variables": {
                "photoId": photo_id,
                "pcursor": pcursor
            },
            "query": self.graphql.get("comment_list")

        }
        return await self.post("", post_data)

    async def get_video_all_comments(self, photo_id: str, crawl_interval: float = 1.0, is_fetch_sub_comments=False,
                                     callback: Optional[Callable] = None):
        """
        get video all comments include sub comments
        :param photo_id:
        :param crawl_interval:
        :param is_fetch_sub_comments:
        :param callback:
        :return:
        """

        result = []
        pcursor = ""
        count = 0

        while pcursor != "no_more" and count < 2:
            comments_res = await self.get_video_comments(photo_id, pcursor)
            vision_commen_list = comments_res.get("visionCommentList", {})
            pcursor = vision_commen_list.get("pcursor", "")
            comments = vision_commen_list.get("rootComments", [])

            if callback:  # 如果有回调函数，就执行回调函数
                await callback(photo_id, comments)

            result.extend(comments)
            await asyncio.sleep(crawl_interval)
            count += 1
            if not is_fetch_sub_comments:
                continue
            # todo handle get sub comments
        return result
