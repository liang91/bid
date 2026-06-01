"""job_logs 表的数据访问对象."""

from sqlalchemy import select

from models import JobLog, JobLogDto
from dao import db
from sqlalchemy import update


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
    def update(id: int, **kwargs) -> bool:
        with db.begin() as session:
            stmt = update(JobLog).where(JobLog.id == id).values(**kwargs)
            res = session.execute(stmt)
            return res.rowcount == 1

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
