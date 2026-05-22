"""公告附件表."""

from datetime import datetime
from model import Base

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship


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
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
