import argparse
import asyncio
import sys

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
        login_type=config.LOGIN_TYPE,
        crawler_type=config.CRAWLER_TYPE
    )
    await crawler.start()

async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Media crawler program.')
    parser.add_argument('--platform', type=str, help='Media platform select (xhs | dy | ks | bili | wb)',
                        choices=["xhs", "dy", "ks", "bili", "wb"], default=config.PLATFORM)
    parser.add_argument('--lt', type=str, help='Login type (qrcode | phone | cookie)',
                        choices=["qrcode", "phone", "cookie"], default=config.LOGIN_TYPE)
    parser.add_argument('--type', type=str, help='crawler type (search | detail | creator)',
                        choices=["search", "detail", "creator"], default=config.CRAWLER_TYPE)
    args = parser.parse_args()
    # 初始化数据库链接
    if config.SAVE_DATA_OPTION == "db":
        await db.init_db()

    task_list = [
        asyncio.create_task(create_crawler_task(platform, config.LOGIN_TYPE, config.CRAWLER_TYPE))
        for platform in args.platform.split(",")
    ]

    await asyncio.wait(task_list)

    if config.SAVE_DATA_OPTION == "db":
        await db.close()


if __name__ == '__main__':
    try:
        # asyncio.run(main()) #事件循环异常关闭
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        sys.exit()
