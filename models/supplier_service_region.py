"""供应商可服务地区表."""

from datetime import datetime
from typing import Optional
from models import Base

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class SupplierServiceRegion(Base):
    __tablename__ = "supplier_service_regions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("supplier.id"), default=0,
                                             comment="供应商ID")
    region_name: Mapped[str] = mapped_column(String(32), default="", comment="地区名称")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")


class SupplierServiceRegionDto(BaseModel):
    """供应商可服务地区数据类."""

    id: Optional[int] = None
    supplier_id: int = 0
    region_name: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
