# -*- coding: utf-8 -*-
# @Author  : 3503222760@qq.com
# @Time    : 2023/12/2 18:44
# @Desc    :

from httpx import RequestError


class DataFetchError(RequestError):
    """something error when fetch"""


class IPBlockError(RequestError):
    """fetch so fast that the server block us ip"""
