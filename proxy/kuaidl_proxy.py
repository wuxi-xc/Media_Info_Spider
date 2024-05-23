# -*- coding: utf-8 -*-
# @Author  : 3503222760@qq.com
# @Time    : 2024/4/5 09:43
# @Desc    : 快代理HTTP实现，官方文档：https://www.kuaidaili.com/?ref=ldwkjqipvz6c
import json
import os
from typing import Dict, List
from urllib.parse import urlencode
import httpx

import config
from tools import utils

from proxy.types import IpInfoModel
from proxy.exception import IpGetError
from base.base import ProxyProvider


class KuaiDaiLiProxy(ProxyProvider):
    def __init__(self, secret_id: str, signature: str, num: int, sep: int):
        """
        快代理HTTP实现
        """
        self.proxy_brand_name = "KUAIDAILI"
        self.api_path = "https://dps.kdlapi.com"
        self.params = {
            "secret_id": secret_id,
            "signature": signature,
            "num": num,
            "format": 'json',
            "sep": sep
        }


    async def get_proxies(self, num: int) -> List[IpInfoModel]:
        """
        :param num:
        :return:
        """
        self.params.update({"num": num})
        ip_infos = []
        async with httpx.AsyncClient() as client:
            url = self.api_path + "/api/getdps" + '?' + urlencode(self.params)
            utils.logger.info(f"[kuaidlProxy.get_proxies] get ip proxy url:{url}")
            response = await client.get(url, headers={
                "User-Agent": "MediaCrawler https://github.com/NanmiCoder/MediaCrawler"})
            res_dict: Dict = response.json()
            if res_dict.get("code") == 0:
                data: List[Dict] = res_dict["data"].get("proxy_list")
                current_ts = utils.get_unix_timestamp()
                for ip_item in data:
                    ip_info_model = IpInfoModel(
                        ip=ip_item.split(":")[0],
                        port=ip_item.split(":")[1],
                        user=config.KUAIDAILI_USER,
                        password=config.KUAIDAILI_PWD,
                    )
                    ip_infos.append(ip_info_model)
            else:
                raise IpGetError(res_dict.get("msg", "unkown err"))
        return ip_infos


def new_kuai_daili_proxy() -> KuaiDaiLiProxy:
    """
    构造快代理HTTP实例
    Returns:

    """
    return KuaiDaiLiProxy(
        secret_id=config.SECRETID,
        signature=config.SECRETKEY,
        num=30,  # 一次提取30个IP
        sep=1  # 代理分割符号
    )
