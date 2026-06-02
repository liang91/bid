"""供应商人员表.

一个供应商可绑定多个人员，企微推送以人员为单位。
"""

from datetime import datetime
from typing import Optional
from models import Base, _DEFAULT_DATETIME

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")

    supplier_id: Mapped[int] = mapped_column(BigInteger, default=0, comment="所属供应商ID")

    # === 基础信息 ===
    name: Mapped[str] = mapped_column(String(64), default="", comment="姓名")
    phone: Mapped[str] = mapped_column(String(20), default="", comment="手机号")
    email: Mapped[str] = mapped_column(String(128), default="", comment="邮箱")

    # === 企业微信绑定（客户联系）===
    wechat_external_userid: Mapped[str] = mapped_column(String(64), default="", comment="个人微信在企业微信中的外部联系人ID")
    wechat_follow_user_id: Mapped[str] = mapped_column(String(64), default="", comment="跟进该人员的我方员工企微UserID")
    wechat_bind_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="企微绑定时间")
    wechat_bind_state: Mapped[str] = mapped_column(String(128), default="", comment="绑定时的二维码state参数")

    # === 状态 ===
    is_primary: Mapped[int] = mapped_column(TINYINT, default=0, comment="是否主要联系人: 1=是 0=否")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="状态: 1=正常 0=禁用")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class UserDto(BaseModel):
    """供应商人员数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    supplier_id: int = 0
    name: str = ""
    phone: str = ""
    email: str = ""
    wechat_external_userid: str = ""
    wechat_follow_user_id: str = ""
    wechat_bind_time: datetime = _DEFAULT_DATETIME
    wechat_bind_state: str = ""
    is_primary: int = 0
    status: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
