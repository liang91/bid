"""匹配结果表."""

from datetime import datetime, date
from typing import Optional
from models import Base, _DEFAULT_DATETIME

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import BigInteger, Date, DateTime, JSON, String, Text, Integer
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class MatchedNotice(BaseModel):
    notice_id: int = 0  # 公告ID
    filter_score: float = 0.0  # 粗筛时，向量相似度
    match_score: int = 0  # ai匹配时，匹配度
    advice: str = ""  # Ai对供应商的投标建议


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    supplier_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="供应商ID")
    day: Mapped[datetime] = mapped_column(Date, comment="日期")
    matched_notices: Mapped[list[MatchedNotice]] = mapped_column(JSON, default=[], comment="粗筛/AI匹配后的公告列表")

    push_status: Mapped[int] = mapped_column(TINYINT, comment="推送状态: 0=未推送 10=已创建素材待员工确认 1=已送达 2=失败")
    push_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="推送时间")
    push_channel: Mapped[str] = mapped_column(String(32), default="", comment="推送渠道")
    push_message_id: Mapped[str] = mapped_column(String(128), default="", comment="推送消息ID")

    user_feedback_score: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户反馈分数")
    user_feedback_comment: Mapped[str] = mapped_column(String(512), default="", comment="用户反馈评论")
    user_viewed: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户是否已查看")
    user_favorite: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户是否已收藏")
    user_applied: Mapped[int] = mapped_column(TINYINT, default=0, comment="用户是否已投标")
    user_feedback_time: Mapped[datetime] = mapped_column(DateTime, default=_DEFAULT_DATETIME, comment="用户反馈时间")

    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="状态")  # 1:新增的匹配任务 20:完成粗筛 30:完成精准匹配

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")


class MatchDto(BaseModel):
    """匹配结果数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    supplier_id: int = 0
    day: date = Field(default_factory=date.today)
    matched_notices: list[MatchedNotice] = []

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
