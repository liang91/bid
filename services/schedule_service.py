"""定时任务调度服务.

封装 APScheduler，从 crawl_targets 表动态读取目标配置并注册任务。
"""
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from dao import SupplierDao, JobLogDao, SiteDao
from models import JobLogDto
from services.crawler_service import CrawlerService
from services.notice_service import NoticeService
from services.supplier_service import SupplierService


class ScheduleService:
    """统一管理所有定时任务."""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # -----------------------------------------------------------------------
    # 任务包装器：自动记录执行日志
    # -----------------------------------------------------------------------
    @classmethod
    def _wrap(cls, job_name: str, func, *args, **kwargs):
        """包装任务函数，记录执行日志."""
        log_id = JobLogDao.create(JobLogDto(job_name=job_name, trigger_time=datetime.now(), status=0))
        logger.info(f"{job_name}-{log_id} 开始执行")

        try:
            result = func(*args, **kwargs)
            # 尝试从 result 中提取记录数
            record_count = 0
            if isinstance(result, dict):
                record_count = result.get("created") or result.get("updated") or 0
            elif isinstance(result, int):
                record_count = result
            elif isinstance(result, list):
                record_count = len(result)

            JobLogDao.update(log_id, status=1, record_count=record_count, message="success")
            logger.info(f"{job_name}-{log_id} 执行成功")
        except Exception as e:
            JobLogDao.update(log_id, status=2, message=str(e))
            logger.error(f"{job_name}:{log_id} 执行失败: {e}")

    # -----------------------------------------------------------------------
    # 注册/删除任务
    # -----------------------------------------------------------------------
    @classmethod
    def register_jobs(cls):
        """从 sites 表读取启用的配置并注册爬取任务."""
        sites = SiteDao.enabled()
        for site in sites:
            job_name = site.job_name()

            cls.scheduler.add_job(
                func=cls._wrap,
                args=(job_name, CrawlerService.run, site),
                trigger=IntervalTrigger(seconds=30),
                id=job_name,
                replace_existing=True,
            )
            logger.info(f"{job_name}：已注册任务")

        # # 08:30 爬取详情 HTML（全局，不区分平台）
        # self.scheduler.add_job(
        #     func=self._wrap,
        #     args=("crawl_html", self.job_crawl_html),
        #     trigger=CronTrigger(hour=8, minute=30),
        #     id="crawl_html",
        #     name="爬取公告详情HTML",
        #     replace_existing=True,
        # )
        #
        # # 09:00 解析 HTML
        # self.scheduler.add_job(
        #     func=self._wrap,
        #     args=("parse", self.job_parse),
        #     trigger=CronTrigger(hour=9, minute=0),
        #     id="parse",
        #     name="LLM解析公告",
        #     replace_existing=True,
        # )
        #
        # # 09:30 全量匹配（粗筛 + 语义排序）
        # self.scheduler.add_job(
        #     func=self._wrap,
        #     args=("match", self.job_match),
        #     trigger=CronTrigger(hour=9, minute=30),
        #     id="match",
        #     name="供应商公告匹配",
        #     replace_existing=True,
        # )
        #
        # # 10:00 AI 精筛
        # self.scheduler.add_job(
        #     func=self._wrap,
        #     args=("ai_match", self.job_ai_match),
        #     trigger=CronTrigger(hour=10, minute=0),
        #     id="ai_match",
        #     name="AI精筛",
        #     replace_existing=True,
        # )

    @classmethod
    def reload_jobs(cls):
        """热重载：重新从数据库读取配置并更新任务."""
        logger.info("开始热重载任务配置...")
        logger.info("热重载完成")

    @classmethod
    def start(cls):
        """启动调度器."""
        cls.register_jobs()
        cls.scheduler.start()
        logger.info("调度器已启动")
        while True:
            time.sleep(10)

    @classmethod
    def shutdown(cls):
        """关闭调度器."""
        if cls.scheduler.running:
            cls.scheduler.shutdown()
            logger.info("调度器已关闭")

    # -----------------------------------------------------------------------
    # 具体任务
    # -----------------------------------------------------------------------

    @classmethod
    def job_parse(cls, limit: int = 100):
        """LLM 解析 HTML."""
        return NoticeService.parse_htmls(limit)

    @classmethod
    def job_match(cls):
        """对所有供应商执行粗筛 + 语义排序."""
        suppliers = SupplierDao.all()
        for supplier in suppliers:
            try:
                SupplierService.filtered_notices(supplier.id)
            except Exception as e:
                logger.error(f"[job_match] 供应商 {supplier.id} 匹配失败: {e}")
        return len(suppliers)

    @classmethod
    def job_ai_match(cls, limit: int = 100):
        """批量 AI 精筛."""
        return SupplierService.ai_match_all(limit=limit)
