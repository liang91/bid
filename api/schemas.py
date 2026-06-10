"""API 请求/响应 Pydantic 模型."""

from typing import Optional, TypeVar, Generic
from pydantic import BaseModel, Field
from decimal import Decimal

T = TypeVar("T")


# ─────────────────────────────────────────
# 通用统一响应包装
# ─────────────────────────────────────────
class Res(BaseModel, Generic[T]):
    """统一接口响应结构."""
    code: int = 0
    msg: str = "success"
    data: Optional[T] = None


# ─────────────────────────────────────────
# Feed
# ─────────────────────────────────────────
class FeedReq(BaseModel):
    user_id: int = 0  # 兼容旧调用，小程序端可不传，由 Token 解析
    limit: int = Field(default=10, ge=1, le=50)
    cursor: Optional[str] = None


class InfoGrid(BaseModel):
    location: str
    area: str
    duration: str
    deposit: dict  # {value: str, alert: bool}


class TimelineItem(BaseModel):
    date: str
    label: str
    alert: bool = False


class Timeline(BaseModel):
    register_deadline: TimelineItem
    bid_deadline: TimelineItem
    open_date: TimelineItem


class Purchaser(BaseModel):
    name: str
    avatar_text: str
    sub: str


class FeedItem(BaseModel):
    notice_id: int
    match_score: int
    match_level: str
    title: str
    tags: list[str]
    is_urgent: bool
    amount: dict  # {label: str, value: int, display: str}
    info_grid: InfoGrid
    timeline: Timeline
    qualifications: list[str]
    description: str
    purchaser: Purchaser
    is_favorite: bool


class FeedRes(BaseModel):
    data: list[FeedItem]
    next_cursor: Optional[str] = None
    has_more: bool


# ─────────────────────────────────────────
# Notices
# ─────────────────────────────────────────
class NoticeDetailRes(BaseModel):
    notice_id: int
    title: str
    tags: list[str]
    amount: dict
    hero_meta: dict
    overview: dict
    qualifications: list[str]
    description: str
    purchaser: dict
    contacts: dict
    attachments: list[dict]
    is_favorite: bool


class FavoriteReq(BaseModel):
    user_id: int = 0  # 兼容旧调用，小程序端可不传，由 Token 解析
    notice_id: int
    action: str = Field(..., pattern="^(add|remove)$")


class FavoriteRes(BaseModel):
    success: bool
    is_favorite: bool


class NoticeDetailReq(BaseModel):
    user_id: int = 0


class NotInterestedReq(BaseModel):
    user_id: int = 0  # 兼容旧调用，小程序端可不传，由 Token 解析
    notice_id: int


# ─────────────────────────────────────────
# Users
# ─────────────────────────────────────────
class FavoriteListItem(BaseModel):
    notice_id: int
    title: str
    amount_display: str
    meta: dict  # {location, bid_deadline, area}
    tags: list[str]


class FavoriteListReq(BaseModel):
    user_id: int = 0  # 兼容旧调用，小程序端可不传，由 Token 解析
    limit: int = 50
    offset: int = 0


class FavoriteListRes(BaseModel):
    total: int
    data: list[FavoriteListItem]


# ─────────────────────────────────────────
# Auth (小程序登录)
# ─────────────────────────────────────────
class WxLoginReq(BaseModel):
    code: str = Field(..., min_length=1, description="小程序 wx.login 获取的临时登录凭证")
    platform: str = ''


class WxLoginRes(BaseModel):
    token: str


# ─────────────────────────────────────────
# Dict
# ─────────────────────────────────────────
class DictItem(BaseModel):
    code: str
    name: str


class DictRes(BaseModel):
    qualifications: list[DictItem]
    business_types: list[DictItem]
    regions: list[DictItem]


class SupplierDictRes(BaseModel):
    qualifications: list[DictItem]
    regions: list[DictItem]

class SupplierProfile(BaseModel):
    supplier_id: int = 0
    company_name: str = Field(default='', min_length=1, max_length=128)
    qualifications: list[str] = []
    business_scopes: list[str] = []
    min_budget: int = 0
    max_budget: int = 999999999
    service_regions: list[str] = []
