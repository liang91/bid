"""公告分包表."""

from datetime import datetime
from decimal import Decimal
from model import Base

from sqlalchemy import BigInteger, DECIMAL, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


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
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
