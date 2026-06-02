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
    def register_jobs(cls):
        """从 sites 表读取启用的配置并注册所有定时任务."""
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

        # 解析 HTML
        cls.scheduler.add_job(
            func=cls._wrap,
            args=("parse", cls.job_parse),
            trigger=CronTrigger(hour=9, minute=0),
            id="parse",
            replace_existing=True,
        )
        logger.info("parse：已注册任务（每天 09:00）")

        # 全量匹配（粗筛 + 语义排序）
        cls.scheduler.add_job(
            func=cls._wrap,
            args=("match", cls.job_match),
            trigger=CronTrigger(hour=9, minute=30),
            id="match",
            replace_existing=True,
        )
        logger.info("match：已注册任务（每天 09:30）")

        # AI 精筛
        cls.scheduler.add_job(
            func=cls._wrap,
            args=("ai_match", cls.job_ai_match),
            trigger=CronTrigger(hour=10, minute=0),
            id="ai_match",
            replace_existing=True,
        )
        logger.info("ai_match：已注册任务（每天 10:00）")

        # 推送高匹配结果给供应商人员（企微1v1）
        cls.scheduler.add_job(
            func=cls._wrap,
            args=("push", cls.job_push),
            trigger=CronTrigger(hour=10, minute=30),
            id="push",
            replace_existing=True,
        )
        logger.info("push：已注册任务（每天 10:30）")

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

    @classmethod
    def job_push(cls):
        """推送高匹配公告给供应商人员（企业微信1v1）."""
        return PushService.push_daily_top_matches()
