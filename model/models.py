"""SQLAlchemy 2.0 数据模型定义.

所有模型类与 bid_database.sql 中的表一一对应，同时保持与原有 dataclass 接口兼容。
"""
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    DECIMAL,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# 默认时间常量（与数据库默认值保持一致）
# ---------------------------------------------------------------------------
_DEFAULT_DATETIME = datetime(1970, 1, 1, 0, 0, 0)


# ---------------------------------------------------------------------------
# 声明式基类
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 招标公告主表
# ---------------------------------------------------------------------------
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
            # 保持与原有 dataclass asdict 行为一致：Decimal 保持原样，datetime 保持原样
            result[col.name] = val
        # 兼容原有爬虫辅助字段
        result["attachments"] = getattr(self, "attachments", [])
        return result

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        """转换为 JSON 字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)


# ---------------------------------------------------------------------------
# 公告资质要求表
# ---------------------------------------------------------------------------
class NoticeQualification(Base):
    __tablename__ = "notice_qualifications"
    __table_args__ = (
        Index("idx_notice_qual", "notice_id", "qualification_type"),
        Index("idx_qual_name", "name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("procurement_notices.id"), default=0)
    qualification_type: Mapped[str] = mapped_column(String(32), default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    required_scope: Mapped[str] = mapped_column(String(256), default="")
    valid_required: Mapped[int] = mapped_column(TINYINT, default=1)
    evidence_type: Mapped[str] = mapped_column(String(64), default="")
    joint_bid_acceptable: Mapped[int] = mapped_column(TINYINT, default=0)
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    notice: Mapped["ProcurementNotice"] = relationship(back_populates="qualifications_rel")

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)


# ---------------------------------------------------------------------------
# 公告附件表
# ---------------------------------------------------------------------------
class NoticeAttachment(Base):
    __tablename__ = "notice_attachments"
    __table_args__ = (Index("idx_notice_id", "notice_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("procurement_notices.id"), default=0)
    name: Mapped[str] = mapped_column(String(256), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    object_key: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    notice: Mapped["ProcurementNotice"] = relationship(back_populates="attachments_rel")

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)


# ---------------------------------------------------------------------------
# 公告分包表
# ---------------------------------------------------------------------------
class NoticePackage(Base):
    __tablename__ = "notice_packages"
    __table_args__ = (Index("idx_notice_pkg", "notice_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("procurement_notices.id"), default=0)
    no: Mapped[str] = mapped_column(String(16), default="")
    name: Mapped[str] = mapped_column(String(256), default="")
    budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"))
    max_limit: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"))
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), default=Decimal("0.0000"))
    unit: Mapped[str] = mapped_column(String(32), default="")

    notice: Mapped["ProcurementNotice"] = relationship(back_populates="packages_rel")

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)


# ---------------------------------------------------------------------------
# 供应商画像表
# ---------------------------------------------------------------------------
class SupplierProfile(Base):
    __tablename__ = "supplier_profiles"
    __table_args__ = (
        Index("idx_region", "province", "city"),
        Index("ft_business_scope", "business_scope", mysql_prefix="FULLTEXT"),
        Index("ft_qualification_summary", "qualification_summary", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # === 公司基本信息 ===
    company_name: Mapped[str] = mapped_column(String(128), default="")
    company_scale: Mapped[str] = mapped_column(String(32), default="")
    province: Mapped[str] = mapped_column(String(32), default="")
    city: Mapped[str] = mapped_column(String(32), default="")
    district: Mapped[str] = mapped_column(String(32), default="")

    # === 身份标签 ===
    sme_status: Mapped[int] = mapped_column(TINYINT, default=0)
    ca_ready: Mapped[int] = mapped_column(TINYINT, default=0)

    # === 业务范围 ===
    business_scope: Mapped[Optional[str]] = mapped_column(Text)
    business_embedding: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # === 资质证书 ===
    qualifications: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    qualification_summary: Mapped[str] = mapped_column(String(512), default="")

    # === 需求偏好 ===
    min_budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"))
    max_budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("999999999.99"))
    preferred_methods: Mapped[str] = mapped_column(String(128), default="")

    # === 联合体 ===
    joint_bid_willing: Mapped[int] = mapped_column(TINYINT, default=0)

    # === 排除项 ===
    excluded_keywords: Mapped[str] = mapped_column(String(256), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # === Relationships ===
    service_regions_rel: Mapped[List["SupplierServiceRegion"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)


# ---------------------------------------------------------------------------
# 供应商可服务地区表
# ---------------------------------------------------------------------------
class SupplierServiceRegion(Base):
    __tablename__ = "supplier_service_regions"
    __table_args__ = (
        Index("idx_supplier_id", "supplier_id"),
        Index("idx_region_name", "region_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("supplier_profiles.id"), default=0)
    region_name: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    supplier: Mapped["SupplierProfile"] = relationship(back_populates="service_regions_rel")

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)


# ---------------------------------------------------------------------------
# 匹配结果表
# ---------------------------------------------------------------------------
class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("supplier_id", "notice_id", name="uk_supplier_notice"),
        Index("idx_supplier_id", "supplier_id"),
        Index("idx_notice_id", "notice_id"),
        Index("idx_ai_level", "ai_match_level"),
        Index("idx_final_score", "final_score"),
        Index("idx_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    supplier_id: Mapped[int] = mapped_column(BigInteger, default=0)
    notice_id: Mapped[int] = mapped_column(BigInteger, default=0)

    ai_match_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), default=Decimal("0.00"))
    ai_match_level: Mapped[str] = mapped_column(String(16), default="")
    ai_match_reasons: Mapped[Optional[str]] = mapped_column(Text)
    ai_risk_tips: Mapped[Optional[str]] = mapped_column(Text)
    ai_key_matching_points: Mapped[Optional[str]] = mapped_column(Text)
    ai_mismatch_points: Mapped[Optional[str]] = mapped_column(Text)
    ai_recommendation: Mapped[str] = mapped_column(String(64), default="")
    ai_raw_response: Mapped[Optional[str]] = mapped_column(Text)
    ai_call_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)

    final_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), default=Decimal("0.00"))
    final_rank: Mapped[int] = mapped_column(BigInteger, default=0)
    is_top3: Mapped[int] = mapped_column(TINYINT, default=0)

    push_status: Mapped[int] = mapped_column(TINYINT, default=0)
    push_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)
    push_channel: Mapped[str] = mapped_column(String(32), default="")
    push_message_id: Mapped[str] = mapped_column(String(128), default="")

    user_feedback_score: Mapped[int] = mapped_column(TINYINT, default=0)
    user_feedback_comment: Mapped[str] = mapped_column(String(512), default="")
    user_viewed: Mapped[int] = mapped_column(TINYINT, default=0)
    user_favorite: Mapped[int] = mapped_column(TINYINT, default=0)
    user_applied: Mapped[int] = mapped_column(TINYINT, default=0)
    user_feedback_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME)

    status: Mapped[int] = mapped_column(TINYINT, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
