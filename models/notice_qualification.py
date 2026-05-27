"""公告资质要求表."""

from typing import Optional
from models import Base

from pydantic import BaseModel
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class NoticeQualification(Base):
    __tablename__ = "notice_qualifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("procurement_notices.id"), default=0,
                                           comment="公告ID")
    qualification_type: Mapped[str] = mapped_column(String(32), default="", comment="资质类型")
    name: Mapped[str] = mapped_column(String(128), default="", comment="资质名称")


class NoticeQualificationDto(BaseModel):
    """公告资质要求数据类."""

    id: Optional[int] = None
    notice_id: int = 0
    qualification_type: str = ""
    name: str = ""
