from loguru import logger
from crawlers import CCGPCrawler


class CrawlerService:

    @staticmethod
    def run(part: str, step: str, size: int):
        crawler = CCGPCrawler(part)

        if step == "list":
            logger.info(">>> 执行第1步: fetch_list (爬取列表页，保存概要信息)")
            result = crawler.fetch_list(pages=size)
            logger.info(f"[爬取结果] {result}")
        elif step == "html":
            logger.info(">>> 执行第2步: fetch_html (获取详情页 HTML，status=1 → 20)")
            result = crawler.fetch_html(limit=size)
            logger.info(f"[爬取结果] {result}")
