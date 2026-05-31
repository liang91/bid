import importlib
from loguru import logger
from models import SiteDto


class CrawlerService:

    @staticmethod
    def get_crawler(site: SiteDto):
        """根据 target 配置动态加载爬虫类."""
        job_name = site.job_name()
        if not site.crawler:
            logger.warning(f"{job_name}未配置 crawler")
            return

        try:
            module = importlib.import_module('crawlers')
            cls = getattr(module, site.crawler)
            return cls(site)
        except Exception as e:
            logger.error(f"{job_name}加载爬虫类失败{site.crawler}: {e}")
            return None

    @staticmethod
    def run(site: SiteDto) -> dict:
        job_name = site.job_name()
        crawler = CrawlerService.get_crawler(site)

        logger.info(f"{job_name}开始爬取")
        if site.action == "fetch_list":
            result = crawler.fetch_list()
        elif site.action == "fetch_html":
            result = crawler.fetch_html()
        else:
            raise ValueError(f"不支持的的动作")
        logger.info(f"{job_name}爬取结果:{result}")
        return result
