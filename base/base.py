from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from proxy.types import IpInfoModel
from playwright.async_api import BrowserContext, BrowserType


class AbstractCrawler(ABC):
    @abstractmethod
    def init_config(self, platform: str, login_type: str, crawler_type: str):
        pass

    @abstractmethod
    async def start(self):
        pass

    @abstractmethod
    async def search(self):
        pass

    @abstractmethod
    async def launch_browser(self, chromium: BrowserType, playwright_proxy: Optional[Dict], user_agent: Optional[str],
                             headless: bool = True) -> BrowserContext:
        pass


class AbstractLogin(ABC):
    @abstractmethod
    async def begin(self):
        pass

    @abstractmethod
    async def login_by_qrcode(self):
        pass

    @abstractmethod
    async def login_by_mobile(self):
        pass

    @abstractmethod
    async def login_by_cookies(self):
        pass


class AbstractStore(ABC):
    @abstractmethod
    async def store_content(self, content_item: Dict):
        pass

    @abstractmethod
    async def store_comment(self, comment_item: Dict):
        pass

    # TODO support all platform
    # only xhs is supported, so @abstractmethod is commented
    # @abstractmethod
    async def store_creator(self, creator: Dict):
        pass


class AbstactApiClient(ABC):
    @abstractmethod
    async def request(self, method, url, **kwargs):
        pass

    @abstractmethod
    async def update_cookies(self, browser_context: BrowserContext):
        pass

    @abstractmethod
    async def pong(self):
        pass


class ProxyProvider(ABC):
    @abstractmethod
    async def get_proxies(self, num: int) -> List[IpInfoModel]:
        """
        获取 IP 的抽象方法，不同的 HTTP 代理商需要实现该方法
        :param num: 提取的 IP 数量
        :return:
        """
        pass