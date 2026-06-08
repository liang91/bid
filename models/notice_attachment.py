"""公告附件表."""

from datetime import datetime
from typing import Optional
from models import Base, DefaultDto

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class NoticeAttachment(Base):
    __tablename__ = "notice_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("notices.id"), default=0,
                                           comment="公告ID")
    name: Mapped[str] = mapped_column(String(256), default="", comment="附件名称")
    url: Mapped[str] = mapped_column(String(512), default="", comment="附件URL")
    object_key: Mapped[str] = mapped_column(String(256), default="", comment="对象存储Key")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")


class NoticeAttachmentDto(DefaultDto):
    """公告附件数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    notice_id: int = 0
    name: str = ""
    url: str = ""
    object_key: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
