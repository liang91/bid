"""用户-公告互动表."""

from datetime import datetime
from typing import Optional

from models import Base, _DEFAULT_DATETIME

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import BigInteger, DateTime
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class UserNoticeInteraction(Base):
    __tablename__ = "user_notice_interactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="用户ID")
    notice_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="公告ID")

    is_viewed: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否已浏览: 1=是 0=否")
    is_favorite: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否收藏: 1=是 0=否")
    is_not_interested: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否标记不感兴趣: 1=是 0=否")
    is_applied: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否已投标: 1=是 0=否")

    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="浏览时间")
    favorited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="收藏时间")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")


class UserNoticeInteractionDto(BaseModel):
    """用户-公告互动数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: int = 0
    notice_id: int = 0
    is_viewed: int = 0
    is_favorite: int = 0
    is_not_interested: int = 0
    is_applied: int = 0
    viewed_at: datetime = _DEFAULT_DATETIME
    favorited_at: datetime = _DEFAULT_DATETIME
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
