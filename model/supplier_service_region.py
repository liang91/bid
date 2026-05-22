"""供应商可服务地区表."""

from datetime import datetime
from model import Base

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


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
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
