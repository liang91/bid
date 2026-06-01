"""任务执行日志表."""

from datetime import datetime
from typing import Optional

from models import Base, _DEFAULT_DATETIME

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    job_name: Mapped[str] = mapped_column(String(64), default="", comment="任务名称")
    trigger_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="计划触发时间")
    status: Mapped[int] = mapped_column(TINYINT, default=0, comment="状态: 0=运行中 1=成功 2=失败")
    record_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="处理记录数")
    message: Mapped[Optional[str]] = mapped_column(Text, comment="日志消息/异常堆栈")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")


class JobLogDto(BaseModel):
    """任务日志数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    job_name: str = ""
    trigger_time: datetime = Field(default_factory=datetime.now)
    status: int = 0
    record_count: int = 0
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
