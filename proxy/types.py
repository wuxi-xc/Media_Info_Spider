# -*- coding: utf-8 -*-
# @Author  : 3503222760@qq.com
# @Time    : 2024/4/5 10:18
# @Desc    : 基础类型
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProviderNameEnum(Enum):
    JISHU_HTTP_PROVIDER: str = "jishuhttp"
    KUAI_DAILI_PROVIDER: str = "kuaidaili"


class IpInfoModel(BaseModel):
    ip: str = Field(title="ip")
    port: int = Field(title="端口")
    user: str = Field(title="IP代理认证的用户名")
    password: str = Field(title="IP代理认证用户的密码")
    protocol: str = Field(default="https://", title="代理IP的协议")
    expired_time_ts: Optional[int] = Field(title="IP 过期时间")


