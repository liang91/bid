"""招标公告主表."""

import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from model import Base, _DEFAULT_DATETIME

from sqlalchemy import (
    BigInteger,
    DECIMAL,
    DateTime,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ProcurementNotice(Base):
    __tablename__ = "procurement_notices"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.attachments = []
    __table_args__ = (
        UniqueConstraint("url", name="uk_url"),
        Index("idx_notice_date", "notice_date"),
        Index("idx_bid_deadline", "bid_deadline"),
        Index("idx_region", "region_province", "region_city", "region_district"),
        Index("idx_budget", "budget"),
        Index("idx_method", "method"),
        Index("idx_category", "category_code"),
        Index("idx_status", "status"),
        Index("ft_project_name", "project_name", mysql_prefix="FULLTEXT"),
        Index("ft_abstract", "abstract", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # === 来源信息 ===
    platform: Mapped[str] = mapped_column(String(64), default="")
    part: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    notice_type: Mapped[str] = mapped_column(String(32), default="")

    # === 核心信息 ===
    url: Mapped[str] = mapped_column(String(256), default="")

    # === 地区 ===
    region_province: Mapped[str] = mapped_column(String(32), default="")
    region_city: Mapped[str] = mapped_column(String(32), default="")
    region_district: Mapped[str] = mapped_column(String(32), default="")

    # === 项目信息 ===
    project_name: Mapped[str] = mapped_column(String(256), default="")
    project_no: Mapped[str] = mapped_column(String(128), default="")
    purchase_plan_no: Mapped[str] = mapped_column(String(128), default="")

    # === 金额 ===
    budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"))
    max_limit: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(8), default="CNY")

    # === 品目 ===
    category_code: Mapped[str] = mapped_column(String(32), default="")
    category_name: Mapped[str] = mapped_column(String(128), default="")
    category_embedding: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # === 采购方式 ===
    method: Mapped[str] = mapped_column(String(32), default="")
    joint_bid_allowed: Mapped[int] = mapped_column(TINYINT, default=0)
    joint_bid_max_members: Mapped[int] = mapped_column(BigInteger, default=0)
    sme_oriented: Mapped[int] = mapped_column(TINYINT, default=0)

    # === 时间节点 ===
    notice_date: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)
    doc_obtain_start: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)
    doc_obtain_end: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)
    bid_deadline: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)
    bid_open_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)

    # === 投标方式 ===
    bid_platform: Mapped[str] = mapped_column(String(128), default="")
    bid_platform_url: Mapped[str] = mapped_column(String(256), default="")
    ca_required: Mapped[int] = mapped_column(TINYINT, default=0)
    doc_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=Decimal("0.00"))

    # === 采购方信息 ===
    purchaser_name: Mapped[str] = mapped_column(String(128), default="")
    purchaser_address: Mapped[str] = mapped_column(String(256), default="")
    purchaser_contact_person: Mapped[str] = mapped_column(String(64), default="")
    purchaser_contact_phone: Mapped[str] = mapped_column(String(32), default="")
    purchaser_region: Mapped[str] = mapped_column(String(64), default="")

    # === 代理机构信息 ===
    agency_name: Mapped[str] = mapped_column(String(128), default="")
    agency_address: Mapped[str] = mapped_column(String(256), default="")
    agency_contact_person: Mapped[str] = mapped_column(String(64), default="")
    agency_contact_phone: Mapped[str] = mapped_column(String(32), default="")
    agency_region: Mapped[str] = mapped_column(String(64), default="")

    # === 项目联系人 ===
    project_contact_person: Mapped[str] = mapped_column(String(64), default="")
    project_contact_phone: Mapped[str] = mapped_column(String(32), default="")

    # === 匹配特征 ===
    qualification_summary: Mapped[Optional[str]] = mapped_column(Text)
    industry_tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    suggested_company_types: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    geographic_advantage: Mapped[str] = mapped_column(String(32), default="")

    # === 原始摘要 ===
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    html: Mapped[Optional[str]] = mapped_column(Text)
    parse_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)

    # === 状态 ===
    status: Mapped[int] = mapped_column(TINYINT, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # === Relationships ===
    attachments_rel: Mapped[List["NoticeAttachment"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan", lazy="selectin"
    )
    packages_rel: Mapped[List["NoticePackage"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan", lazy="selectin"
    )
    qualifications_rel: Mapped[List["NoticeQualification"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        """转换为字典（不包含 relationship，避免循环引用）."""
        result = {}
        for col in self.__table__.columns:
            val = getattr(self, col.name)
            result[col.name] = val
        result["attachments"] = getattr(self, "attachments", [])
        return result

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        """转换为 JSON 字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
