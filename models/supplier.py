"""供应商画像表."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from models import Base

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Integer, BigInteger, DateTime, DECIMAL, LargeBinary, JSON, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    # === 公司基本信息 ===
    company_name: Mapped[str] = mapped_column(String(128), default="", comment="公司名称")
    company_scale: Mapped[str] = mapped_column(String(32), default="", comment="公司规模")
    province: Mapped[str] = mapped_column(String(32), default="", comment="省份")
    city: Mapped[str] = mapped_column(String(32), default="", comment="城市")
    district: Mapped[str] = mapped_column(String(32), default="", comment="区县")

    # === 身份标签 ===
    sme_status: Mapped[int] = mapped_column(TINYINT, default=0, comment="中小企业状态")
    ca_ready: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否具备CA")

    # === 业务范围 ===
    business_scope: Mapped[Optional[str]] = mapped_column(Text, comment="业务范围")
    service_regions: Mapped[list[str]] = mapped_column(JSON, default=[], comment="可服务地区列表")
    profile_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, comment="供应商画像语义向量")

    # === 资质证书 ===
    qualifications: Mapped[Optional[list]] = mapped_column(JSON, default=[], comment="资质证书列表")
    qualification_summary: Mapped[str] = mapped_column(String(512), default="", comment="资质摘要")

    # === 需求偏好 ===
    min_budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"), comment="最小预算")
    max_budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("999999999.99"), comment="最大预算")
    preferred_methods: Mapped[str] = mapped_column(String(128), default="", comment="偏好采购方式")

    # === 联合体 ===
    joint_bid_willing: Mapped[int] = mapped_column(Integer, default=0, comment="是否愿意联合投标")

    # === 排除项 ===
    excluded_keywords: Mapped[str] = mapped_column(String(256), default="", comment="排除关键词")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")

class SupplierQualification(BaseModel):
    name: str = ''
    cert_no: str = ''
    valid_until: str = ''

class SupplierDto(BaseModel):
    """供应商画像数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    company_name: str = ""
    company_scale: str = ""
    province: str = ""
    city: str = ""
    district: str = ""
    sme_status: int = 0
    ca_ready: int = 0
    business_scope: str = ""
    service_regions: list[str] = []
    profile_embedding: bytes | None = None
    qualifications: list[SupplierQualification] = []
    qualification_summary: str = ""
    min_budget: Decimal = Decimal("0.00")
    max_budget: Decimal = Decimal("999999999.99")
    preferred_methods: str = ""
    joint_bid_willing: int = 0
    excluded_keywords: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
