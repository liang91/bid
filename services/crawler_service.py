import importlib
from datetime import datetime

from loguru import logger

from dao import SiteDao, JobLogDao
from models import SiteDto, JobLogDto


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
            logger.error(f"{job_name}加载爬虫类失败: {e}")
            return None

    @classmethod
    def crawl(cls):
        sites = SiteDao.enabled()
        sites = sorted(sites, key=lambda row: row.priority)
        for site in sites:
            job_name = site.job_name()
            log_id = JobLogDao.create(JobLogDto(job_name=job_name, trigger_time=datetime.now(), status=0))
            logger.info(f"{job_name}-{log_id} 开始执行")

            try:
                crawler = cls.get_crawler(site)
                logger.info(f"{job_name}开始爬取")
                if site.action == "fetch_list":
                    result = crawler.fetch_list()
                elif site.action == "fetch_html":
                    result = crawler.fetch_html()
                else:
                    raise ValueError(f"不支持的的动作")

                count = 0
                if isinstance(result, dict):
                    count = result.get("created") or result.get("updated") or 0

                JobLogDao.update(log_id, status=1, record_count=count, message="success")
                logger.info(f"{job_name}-{log_id} 执行成功")
            except Exception as e:
                JobLogDao.update(log_id, status=2, message=str(e))
                logger.error(f"{job_name}:{log_id} 执行失败: {e}")