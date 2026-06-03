from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, DateTime, String


from models import Base


class LatestUrl(Base):
    __tablename__ = "latest_urls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default='', comment='平台')
    part: Mapped[str] = mapped_column(String(32), nullable=False, default='', comment='栏目')
    url: Mapped[str] = mapped_column(String(256), nullable=False, default='', comment='上次爬取的最新链接')
    updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    created: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment='创建时间')


class LatestUrlDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    platform: str = ''
    part: str = ''
    url: str = ''
    updated: datetime = Field(default_factory=datetime.now)
    created: datetime = Field(default_factory=datetime.now)