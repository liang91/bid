"""供应商画像表."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from model import Base

from sqlalchemy import BigInteger, DateTime, DECIMAL, Index, JSON, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship


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
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
