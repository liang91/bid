"""定时任务管理器.

封装 APScheduler，定义每日任务流水线。
"""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from dao import SupplierDao, JobLogDao
from models import JobLogDto
from services import ClawerService, NoticeService, SupplierService


class JobManager:
    """统一管理所有定时任务."""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # -----------------------------------------------------------------------
    # 任务包装器：自动记录执行日志
    # -----------------------------------------------------------------------
    @staticmethod
    def _wrap(job_name: str, func, *args, **kwargs):
        """包装任务函数，记录执行日志."""
        log_dto = JobLogDto(job_name=job_name, trigger_time=datetime.now(), status=0)
        log_id = JobLogDao.create(log_dto)
        logger.info(f"[Scheduler] 任务 {job_name} 开始执行")

        try:
            result = func(*args, **kwargs)
            # 尝试从 result 中提取记录数
            record_count = 0
            if isinstance(result, dict):
                record_count = result.get("crawled") or result.get("inserted") or result.get("total") or result.get("success") or 0
            elif isinstance(result, int):
                record_count = result
            elif isinstance(result, list):
                record_count = len(result)

            JobLogDao.update(
                JobLogDto(id=log_id, status=1, record_count=record_count, message="执行成功")
            )
            logger.info(f"[Scheduler] 任务 {job_name} 执行成功")
        except Exception as e:
            JobLogDao.update(
                JobLogDto(id=log_id, status=2, message=str(e))
            )
            logger.error(f"[Scheduler] 任务 {job_name} 执行失败: {e}")

    # -----------------------------------------------------------------------
    # 具体任务
    # -----------------------------------------------------------------------
    @staticmethod
    def job_crawl_list(part: str = "dfgg", pages: int = 2):
        """爬取公告列表."""
        return ClawerService.run(part, "list", pages)

    @staticmethod
    def job_crawl_html(part: str = "dfgg", limit: int = 100):
        """爬取公告详情页 HTML."""
        return ClawerService.run(part, "html", limit)

    @staticmethod
    def job_parse(limit: int = 100):
        """LLM 解析 HTML."""
        return NoticeService.parse_htmls(limit)

    @staticmethod
    def job_match():
        """对所有供应商执行粗筛 + 语义排序."""
        suppliers = SupplierDao.all()
        for supplier in suppliers:
            try:
                SupplierService.filtered_notices(supplier.id)
            except Exception as e:
                logger.error(f"[job_match] 供应商 {supplier.id} 匹配失败: {e}")
        return len(suppliers)

    @staticmethod
    def job_ai_match(limit: int = 100):
        """批量 AI 精筛."""
        return SupplierService.ai_match_all(limit=limit)

    # -----------------------------------------------------------------------
    # 注册任务到调度器
    # -----------------------------------------------------------------------
    def register_jobs(self):
        """注册每日任务流水线."""
        # 08:00 爬取列表
        self.scheduler.add_job(
            func=self._wrap,
            args=("crawl_list", self.job_crawl_list),
            trigger=CronTrigger(hour=8, minute=0),
            id="crawl_list",
            name="爬取公告列表",
            replace_existing=True,
        )

        # 08:30 爬取详情 HTML
        self.scheduler.add_job(
            func=self._wrap,
            args=("crawl_html", self.job_crawl_html),
            trigger=CronTrigger(hour=8, minute=30),
            id="crawl_html",
            name="爬取公告详情HTML",
            replace_existing=True,
        )

        # 09:00 解析 HTML
        self.scheduler.add_job(
            func=self._wrap,
            args=("parse", self.job_parse),
            trigger=CronTrigger(hour=9, minute=0),
            id="parse",
            name="LLM解析公告",
            replace_existing=True,
        )

        # 09:30 全量匹配（粗筛 + 语义排序）
        self.scheduler.add_job(
            func=self._wrap,
            args=("match", self.job_match),
            trigger=CronTrigger(hour=9, minute=30),
            id="match",
            name="供应商公告匹配",
            replace_existing=True,
        )

        # 10:00 AI 精筛
        self.scheduler.add_job(
            func=self._wrap,
            args=("ai_match", self.job_ai_match),
            trigger=CronTrigger(hour=10, minute=0),
            id="ai_match",
            name="AI精筛",
            replace_existing=True,
        )

        # 10:30 企业微信推送（预留，待推送模块完成后接入）
        # self.scheduler.add_job(
        #     func=self._wrap,
        #     args=("push", self.job_push),
        #     trigger=CronTrigger(hour=10, minute=30),
        #     id="push",
        #     name="企业微信推送",
        #     replace_existing=True,
        # )

        logger.info("[Scheduler] 所有任务已注册")

    def start(self):
        """启动调度器."""
        self.register_jobs()
        self.scheduler.start()
        logger.info("[Scheduler] 调度器已启动")

    def shutdown(self):
        """关闭调度器."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("[Scheduler] 调度器已关闭")
