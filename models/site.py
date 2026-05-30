"""爬虫目标网站配置表."""

from datetime import datetime
from typing import Optional

from models import Base

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import BigInteger, DateTime, JSON, String, Integer
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    platform: Mapped[str] = mapped_column(String(64), default="", comment="网站名称，如：中国政府采购网")
    part: Mapped[str] = mapped_column(String(32), default="", comment="栏目名称，如：地方公告")
    action: Mapped[str] = mapped_column(String(32), default="", comment="执行的动作，如：fetch_list,fetch_html")
    crawler: Mapped[str] = mapped_column(String(128), default="", comment="爬虫类全路径，如：crawlers.ccgp_crawler.CCGPCrawler")
    url: Mapped[str] = mapped_column(String(256), default="", comment="网站基础URL")

    enabled: Mapped[int] = mapped_column(TINYINT, default=1, comment="是否启用：0禁用 1启用")
    schedule_type: Mapped[str] = mapped_column(String(16), default="interval", comment="调度类型：interval/cron")
    schedule_config: Mapped[dict] = mapped_column(JSON, comment="调度配置，如：{minutes: 60} 或 {hour: 8, minute: 30}")

    pages: Mapped[int] = mapped_column(BigInteger, default=10, comment="每次爬取页数")
    delay: Mapped[int] = mapped_column(Integer, default=1, comment="请求间隔（秒）")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class SiteDto(BaseModel):
    """爬虫目标配置数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    platform: str = ""
    part: str = ""
    action: str = "fetch_list"
    crawler: str = ""
    url: str = ""
    enabled: int = 1
    schedule_type: str = "interval"
    schedule_config: dict = {}

    pages: int = 10
    delay: int = 1

    fetch_detail: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
