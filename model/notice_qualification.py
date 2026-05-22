"""公告资质要求表."""

from datetime import datetime
from model import Base

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship


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
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
