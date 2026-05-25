"""招标公告主表."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Optional
from model import Base, _DEFAULT_DATETIME

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import BigInteger, DECIMAL, DateTime, JSON, LargeBinary, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class ProcurementNotice(Base):
    __tablename__ = "procurement_notices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    # === 来源信息 ===
    platform: Mapped[str] = mapped_column(String(64), default="", comment="招标信息发布平台")
    part: Mapped[str] = mapped_column(String(32), default="", comment="发布平台栏目")
    title: Mapped[str] = mapped_column(String(256), default="", comment="公告标题")
    notice_type: Mapped[str] = mapped_column(String(32), default="", comment="公告类型：招标/中标/合同公示/中止/改动")

    # === 核心信息 ===
    url: Mapped[str] = mapped_column(String(256), default="", comment="公告网页链接")

    # === 地区 ===
    region_province: Mapped[str] = mapped_column(String(32), default="", comment="采购方所在省份")
    region_city: Mapped[str] = mapped_column(String(32), default="", comment="采购方所在城市")
    region_district: Mapped[str] = mapped_column(String(32), default="", comment="采购方所在县区")

    # === 项目信息 ===
    project_name: Mapped[str] = mapped_column(String(256), default="", comment="采购项目名称")
    project_no: Mapped[str] = mapped_column(String(128), default="", comment="采购项目号")
    purchase_plan_no: Mapped[str] = mapped_column(String(128), default="", comment="采购计划编号")

    # === 金额 ===
    budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"), comment="采购预算金额")
    currency: Mapped[str] = mapped_column(String(8), default="CNY", comment="币种")

    # === 采购方式 ===
    method: Mapped[str] = mapped_column(String(32), default="", comment="采购方式")
    joint_bid_allowed: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否允许联合投标")
    joint_bid_max_members: Mapped[int] = mapped_column(BigInteger, default=0, comment="联合投标最多参与方数量")
    sme_oriented: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否专门面向中小企业")

    # === 时间节点 ===
    notice_date: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="公告发布时间")
    doc_obtain_start: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME,
                                                       comment="获取招标文件开始时间")
    doc_obtain_end: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME,
                                                     comment="获取招标文件截止时间")
    bid_deadline: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="招标截止时间")
    bid_open_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="开标时间")

    # === 投标方式 ===
    bid_platform: Mapped[str] = mapped_column(String(128), default="", comment="投标平台")
    bid_platform_url: Mapped[str] = mapped_column(String(256), default="", comment="投标平台网址")
    ca_required: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否需要CA")
    doc_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=Decimal("0.00"),
                                               comment="招标文件价格")

    # === 采购方信息 ===
    purchaser_name: Mapped[str] = mapped_column(String(128), default="", comment="采购方名称")
    purchaser_address: Mapped[str] = mapped_column(String(256), default="", comment="采购方地址")
    purchaser_contact_person: Mapped[str] = mapped_column(String(64), default="", comment="采购方联系人")
    purchaser_contact_phone: Mapped[str] = mapped_column(String(32), default="", comment="采购方联系电话")
    # === 代理机构信息 ===
    agency_name: Mapped[str] = mapped_column(String(128), default="", comment="代理机构名称")
    agency_address: Mapped[str] = mapped_column(String(256), default="", comment="代理机构地址")
    agency_contact_person: Mapped[str] = mapped_column(String(64), default="", comment="代理机构联系人")
    agency_contact_phone: Mapped[str] = mapped_column(String(32), default="",
                                                      comment="代理机构联系电话")
    # === 项目联系人 ===
    project_contact_person: Mapped[str] = mapped_column(String(64), default="", comment="采购项目联系人")
    project_contact_phone: Mapped[str] = mapped_column(String(32), default="", comment="采购项目联系电话")

    # === 匹配特征 ===
    qualification_summary: Mapped[Optional[str]] = mapped_column(Text, comment="投标所需资质")
    industry_tags: Mapped[list[str]] = mapped_column(JSON, comment="行业标签")
    supplier_profile: Mapped[str] = mapped_column(String(512), comment="所需供应商画像文本")
    supplier_profile_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary,
                                                                        comment="所需供应商画像语义向量（BLOB存储）")

    # === 原始摘要 ===
    abstract: Mapped[Optional[str]] = mapped_column(Text, default="", comment="公告摘要")
    html: Mapped[Optional[str]] = mapped_column(Text, default="", comment="原始HTML内容")
    parse_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="解析时间")

    # === 状态 ===
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")


class ProcurementNoticeDto(BaseModel):
    """招标公告数据类."""

    id: Optional[int] = None
    platform: str = ""
    part: str = ""
    title: str = ""
    notice_type: str = ""
    url: str = ""
    region_province: str = ""
    region_city: str = ""
    region_district: str = ""
    project_name: str = ""
    project_no: str = ""
    purchase_plan_no: str = ""
    budget: Decimal = Decimal("0.00")
    currency: str = "CNY"
    method: str = ""
    joint_bid_allowed: int = 0
    joint_bid_max_members: int = 0
    sme_oriented: int = 0
    notice_date: datetime = _DEFAULT_DATETIME
    doc_obtain_start: datetime = _DEFAULT_DATETIME
    doc_obtain_end: datetime = _DEFAULT_DATETIME
    bid_deadline: datetime = _DEFAULT_DATETIME
    bid_open_time: datetime = _DEFAULT_DATETIME
    bid_platform: str = ""
    bid_platform_url: str = ""
    ca_required: int = 0
    doc_price: Decimal = Decimal("0.00")
    purchaser_name: str = ""
    purchaser_address: str = ""
    purchaser_contact_person: str = ""
    purchaser_contact_phone: str = ""
    agency_name: str = ""
    agency_address: str = ""
    agency_contact_person: str = ""
    agency_contact_phone: str = ""
    project_contact_person: str = ""
    project_contact_phone: str = ""
    qualification_summary: str = ''
    industry_tags: list[str] = []
    abstract: str = ""
    supplier_profile: str = ''
    supplier_profile_embedding: bytes | None = None
    html: Optional[str] = ""
    parse_time: datetime = Field(default_factory=datetime.now)
    status: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
