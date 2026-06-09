"""定时任务调度服务.

封装 APScheduler，从 crawl_targets 表动态读取目标配置并注册任务。
"""
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from dao import SupplierDao, JobLogDao, SiteDao
from models import JobLogDto
from services.crawler_service import CrawlerService
from services.notice_service import NoticeService
from services.supplier_service import SupplierService
from services.push_service import PushService


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
    def start(cls):
        """从 sites 表读取启用的配置并注册所有定时任务."""
        # 获取符合条件的网页链接&网页内容
        cls.scheduler.add_job(
            func=CrawlerService.crawl,
            trigger=IntervalTrigger(hours=1),
            id='crawl',
            replace_existing=True,
            next_run_time=datetime.now(),
        )
        logger.info("已注册任务:crawl - 每小时执行一次")

        # 通过大模型将网页内容解析成结构化数据
        cls.scheduler.add_job(
            func=cls._wrap,
            args=("parse", NoticeService.parse_htmls),
            trigger=IntervalTrigger(minutes=1),
            id="parse",
            replace_existing=True,
        )
        logger.info("已注册任务:parse - 每10分钟执行一次")

        # # 全量匹配（粗筛 + 语义排序）
        # cls.scheduler.add_job(
        #     func=cls._wrap,
        #     args=("filter", SupplierService.filter_for_all),
        #     trigger=CronTrigger(hour=9, minute=30),
        #     id="filter",
        #     replace_existing=True,
        # )
        # logger.info("已注册任务:filter（每天 09:30）")
        #
        # # AI 精筛
        # cls.scheduler.add_job(
        #     func=cls._wrap,
        #     args=("match", SupplierService.match_all),
        #     trigger=CronTrigger(hour=10, minute=0),
        #     id="match",
        #     replace_existing=True,
        # )
        # logger.info("已注册任务:match（每天 10:00）")

        # 推送高匹配结果给供应商人员（企微1v1）
        # cls.scheduler.add_job(
        #     func=cls._wrap,
        #     args=("push", PushService.push_daily_top_matches),
        #     trigger=CronTrigger(hour=10, minute=30),
        #     id="push",
        #     replace_existing=True,
        # )
        # logger.info("push：已注册任务（每天 10:30）")

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
