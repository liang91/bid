"""匹配结果表."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from models import Base, _DEFAULT_DATETIME

from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, DateTime, DECIMAL, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    supplier_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="供应商ID")
    notice_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="公告ID")

    ai_match_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), default=Decimal("0.00"), comment="AI匹配分数")
    ai_match_level: Mapped[str] = mapped_column(String(16), default="", comment="AI匹配等级")
    ai_match_reasons: Mapped[Optional[str]] = mapped_column(Text, comment="AI匹配原因")
    ai_risk_tips: Mapped[Optional[str]] = mapped_column(Text, comment="AI风险提示")
    ai_key_matching_points: Mapped[Optional[str]] = mapped_column(Text, comment="AI关键匹配点")
    ai_mismatch_points: Mapped[Optional[str]] = mapped_column(Text, comment="AI不匹配点")
    ai_recommendation: Mapped[str] = mapped_column(String(64), default="", comment="AI推荐建议")
    ai_raw_response: Mapped[Optional[str]] = mapped_column(Text, comment="AI原始响应")
    ai_call_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="AI调用时间")

    final_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), default=Decimal("0.00"), comment="最终分数")
    final_rank: Mapped[int] = mapped_column(BigInteger, default=0, comment="最终排名")
    is_top3: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否前三")

    push_status: Mapped[int] = mapped_column(TINYINT, default=0, comment="推送状态")
    push_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="推送时间")
    push_channel: Mapped[str] = mapped_column(String(32), default="", comment="推送渠道")
    push_message_id: Mapped[str] = mapped_column(String(128), default="", comment="推送消息ID")

    user_feedback_score: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户反馈分数")
    user_feedback_comment: Mapped[str] = mapped_column(String(512), default="", comment="用户反馈评论")
    user_viewed: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户是否已查看")
    user_favorite: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户是否已收藏")
    user_applied: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户是否已投标")
    user_feedback_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="用户反馈时间")

    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="状态")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")


class MatchResultDto(BaseModel):
    """匹配结果数据类."""

    id: Optional[int] = None
    supplier_id: int = 0
    notice_id: int = 0
    ai_match_score: Decimal = Decimal("0.00")
    ai_match_level: str = ""
    ai_match_reasons: Optional[str] = None
    ai_risk_tips: Optional[str] = None
    ai_key_matching_points: Optional[str] = None
    ai_mismatch_points: Optional[str] = None
    ai_recommendation: str = ""
    ai_raw_response: Optional[str] = None
    ai_call_time: datetime = _DEFAULT_DATETIME
    final_score: Decimal = Decimal("0.00")
    final_rank: int = 0
    is_top3: int = 0
    push_status: int = 0
    push_time: datetime = _DEFAULT_DATETIME
    push_channel: str = ""
    push_message_id: str = ""
    user_feedback_score: int = 0
    user_feedback_comment: str = ""
    user_viewed: int = 0
    user_favorite: int = 0
    user_applied: int = 0
    user_feedback_time: datetime = _DEFAULT_DATETIME
    status: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
