"""公告分包表."""

from decimal import Decimal
from typing import Optional
from models import Base

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, DECIMAL, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class NoticePackage(Base):
    __tablename__ = "notice_packages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    notice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("notices.id"), default=0,
                                           comment="公告ID")
    no: Mapped[str] = mapped_column(String(16), default="", comment="分包编号")
    name: Mapped[str] = mapped_column(String(256), default="", comment="分包名称")
    budget: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal("0.00"), comment="预算金额")
    quantity: Mapped[str] = mapped_column(String(8), default="", comment="数量")
    unit: Mapped[str] = mapped_column(String(32), default="", comment="单位")


class NoticePackageDto(BaseModel):
    """公告分包数据类."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    notice_id: int = 0
    no: str = ""
    name: str = ""
    budget: Decimal = Decimal("0.00")
    quantity: str = ""
    unit: str = ""
