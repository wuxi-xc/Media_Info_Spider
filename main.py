import asyncio
import sys
import os

import config
import db
from base.base import AbstractCrawler
from media_platform.bilibili import BilibiliCrawler
from media_platform.douyin import DouYinCrawler
from media_platform.kuaishou import KuaishouCrawler
from media_platform.weibo import WeiboCrawler
from media_platform.xhs import XiaoHongShuCrawler


class CrawlerFactory:

    CRAWLERS = {
        "xhs": XiaoHongShuCrawler,
        "douyin": DouYinCrawler,
        "kuaishou": KuaishouCrawler,
        "bilibili": BilibiliCrawler,
        "wb": WeiboCrawler
    }

    # {"code":0,"message":"0","ttl":1,"data":{}}
    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_class = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_class:
            raise ValueError("暂未支持该平台的爬虫")
        return crawler_class()


async def create_crawler_task(platform : str, login_type : str, crawler_type : str):
    crawler = CrawlerFactory.create_crawler(platform=platform)
    crawler.init_config(
        platform=platform,
        login_type=login_type,
        crawler_type=crawler_type
    )
    await crawler.start()

async def main():

    platform = os.environ.get('PLATFORM', config.PLATFORM)
    login_type = os.environ.get('LOGIN_TYPE', config.LOGIN_TYPE)
    crawler_type = os.environ.get('CRAWLER_TYPE', config.CRAWLER_TYPE)

    if config.SAVE_DATA_OPTION == "db":
        await db.init_db()

    await create_crawler_task(platform, login_type, crawler_type)

    if config.SAVE_DATA_OPTION == "db":
        await db.close()


if __name__ == '__main__':
    # os.environ['PLATFORM'] = 'douyin'
    # os.environ['LOGIN_TYPE'] = 'qrcode'
    # os.environ['CRAWLER_TYPE'] = 'login'
    # # os.environ['ENABLE_GET_COMMENTS'] = 'False'
    # os.environ['RESOURCE_NAME'] = '庆余年2'

    try:
        # asyncio.run(main()) #事件循环异常关闭
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        sys.exit()
