import importlib
from loguru import logger
from models import SiteDto


class CrawlerService:

    @staticmethod
    def get_crawler(site: SiteDto):
        """根据 target 配置动态加载爬虫类.

        支持两种配置格式：
        - 类名: CCGPCrawler、BJGGZYCrawler
        - 完整路径: crawlers.ccgp_crawler.CCGPCrawler
        """
        job_name = site.job_name()
        if not site.crawler:
            logger.warning(f"{job_name}未配置 crawler")
            return

        try:
            crawler_path = site.crawler.strip()
            if "." in crawler_path:
                # 完整模块路径: crawlers.ccgp_crawler.CCGPCrawler
                module_path, cls_name = crawler_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                cls = getattr(module, cls_name)
            else:
                # 短类名: CCGPCrawler
                module = importlib.import_module('crawlers')
                cls = getattr(module, crawler_path)
            return cls(site)
        except Exception as e:
            logger.error(f"{job_name}加载爬虫类失败{crawler_path}: {e}")
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
