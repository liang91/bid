import importlib
from loguru import logger
from models import SiteDto


class CrawlerService:

    @staticmethod
    def get_crawler(site: SiteDto):
        """根据 target 配置动态加载爬虫类."""
        if not site.crawler:
            logger.warning(f"[CrawlerService] {site.name}/{site.part} 未配置 crawler")
            return

        try:
            module = importlib.import_module('crawlers')
            cls = getattr(module, site.crawler)
            return cls(site)
        except Exception as e:
            logger.error(f"[CrawlerService] 加载爬虫类失败 {site.crawler}: {e}")
            return None

    @staticmethod
    def run(site: SiteDto) -> dict:
        crawler = CrawlerService.get_crawler(site)

        if site.action == "fetch_list":
            logger.info(f">>> 执行爬取列表: target={site.platform}/{site.part}")
            result = crawler.fetch_list()
            logger.info(f"[爬取结果] {result}")
            return result
        elif site.action == "fetch_html":
            logger.info(f">>> 执行爬取详情页HTML: target={site.platform}/{site.part}")
            result = crawler.fetch_html()
            logger.info(f"[爬取结果] {result}")
            return result
        else:
            raise ValueError(f"不支持的的动作")
