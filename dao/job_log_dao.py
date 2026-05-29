"""job_logs 表的数据访问对象."""

from sqlalchemy import select

from models import JobLog, JobLogDto
from dao import db


class JobLogDao:
    """任务执行日志存储器."""

    @staticmethod
    def create(dto: JobLogDto) -> int:
        with db.begin() as session:
            log = JobLog(**dto.model_dump(exclude={"id", "created_at"}))
            session.add(log)
            session.flush()
            return log.id

    @staticmethod
    def update(dto: JobLogDto) -> bool:
        if not dto.id:
            return False
        with db.begin() as session:
            obj = session.get(JobLog, dto.id)
            if not obj:
                return False
            obj.status = dto.status
            obj.record_count = dto.record_count
            obj.message = dto.message
            return True

    @staticmethod
    def fetch_recent(job_name: str, limit: int = 10) -> list[JobLogDto]:
        """查询某个任务的最近执行记录."""
        with db() as session:
            stmt = (
                select(JobLog)
                .where(JobLog.job_name == job_name)
                .order_by(JobLog.id.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [JobLogDto.model_validate(row) for row in rows]
