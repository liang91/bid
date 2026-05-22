"""匹配结果表."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from model import Base, _DEFAULT_DATETIME

from sqlalchemy import BigInteger, DateTime, DECIMAL, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


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
        import json
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent, default=str)
