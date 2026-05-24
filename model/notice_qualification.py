"""公告资质要求表."""

from datetime import datetime
from typing import Optional
from model import Base

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class NoticeQualification(Base):
    __tablename__ = "notice_qualifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("procurement_notices.id"), default=0,
                                           comment="公告ID")
    qualification_type: Mapped[str] = mapped_column(String(32), default="", comment="资质类型")
    name: Mapped[str] = mapped_column(String(128), default="", comment="资质名称")
    required_scope: Mapped[str] = mapped_column(String(256), default="", comment="资质要求范围")
    valid_required: Mapped[int] = mapped_column(TINYINT, default=1, comment="是否需要有效资质")
    evidence_type: Mapped[str] = mapped_column(String(64), default="", comment="证明材料类型")
    joint_bid_acceptable: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否接受联合投标")
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0, comment="排序序号")


class NoticeQualificationDto(BaseModel):
    """公告资质要求数据类."""

    id: Optional[int] = None
    notice_id: int = 0
    qualification_type: str = ""
    name: str = ""
    required_scope: str = ""
    valid_required: int = 1
    evidence_type: str = ""
    joint_bid_acceptable: int = 0
    sort_order: int = 0
