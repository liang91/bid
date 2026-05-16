"""数据模型定义."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class BidNotice:
    """招标公告数据模型."""

    # 基础信息（列表页获取）
    title: str = ""                           # 标题
    url: str = ""                             # 详情页链接
    notice_type: str = ""                     # 公告类型（公开招标、中标公告等）
    publish_time: str = ""                    # 发布时间
    region: str = ""                          # 地域/省份
    purchaser: str = ""                       # 采购人

    # 详情页信息
    project_name: Optional[str] = None        # 采购项目名称
    category: Optional[str] = None            # 品目
    purchaser_unit: Optional[str] = None      # 采购单位
    administrative_region: Optional[str] = None  # 行政区域
    bid_document_time: Optional[str] = None   # 获取招标文件时间
    bid_document_price: Optional[str] = None  # 招标文件售价
    bid_document_location: Optional[str] = None  # 获取招标文件的地点
    bid_open_time: Optional[str] = None       # 开标时间
    bid_open_location: Optional[str] = None   # 开标地点
    budget_amount: Optional[str] = None       # 预算金额
    total_bid_amount: Optional[str] = None    # 总中标金额
    review_experts: Optional[str] = None      # 评审专家名单
    contact_person: Optional[str] = None      # 项目联系人
    contact_phone: Optional[str] = None       # 项目联系电话
    purchaser_address: Optional[str] = None   # 采购单位地址
    purchaser_contact: Optional[str] = None   # 采购单位联系方式
    agency_name: Optional[str] = None         # 代理机构名称
    agency_address: Optional[str] = None      # 代理机构地址
    agency_contact: Optional[str] = None      # 代理机构联系方式
    content_text: Optional[str] = None        # 正文纯文本内容
    content_html: Optional[str] = None        # 正文HTML内容
    attachments: list = field(default_factory=list)  # 附件列表

    # 解析提取的字段
    province: Optional[str] = None              # 省
    city: Optional[str] = None                  # 市
    district: Optional[str] = None              # 区/县
    publish_time_std: Optional[str] = None      # 发布时间（标准格式 YYYY-MM-DD HH:MM）
    project_code: Optional[str] = None          # 项目编号

    # 采购方信息（标准化）
    purchaser_name: Optional[str] = None        # 采购方名称
    purchaser_address_std: Optional[str] = None # 采购方地址
    purchaser_contact_person: Optional[str] = None  # 采购方联系人
    purchaser_contact_phone: Optional[str] = None   # 采购方联系方式

    # 代理机构信息（标准化）
    agency_name_std: Optional[str] = None       # 代理机构名称
    agency_address_std: Optional[str] = None    # 代理机构地址
    agency_contact_phone: Optional[str] = None  # 代理机构联系方式

    # 项目联系信息（标准化）
    project_contact_person: Optional[str] = None    # 项目联系人
    project_contact_phone: Optional[str] = None     # 项目联系方式

    # 金额（整数分）
    budget_amount_fen: Optional[int] = None     # 采购预算金额（精确到分，整数形式）

    # 采购文件获取时间（拆分）
    bid_doc_start_time: Optional[str] = None    # 采购文件获取开始时间
    bid_doc_end_time: Optional[str] = None      # 采购文件获取截止时间

    # 投标相关
    response_deadline: Optional[str] = None     # 响应文件提交截止时间
    bid_start_time: Optional[str] = None        # 投标开始时间
    bid_location_std: Optional[str] = None      # 投标地点

    # 元数据
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "中国政府采购网"             # 数据来源
    list_page: str = ""                       # 来源列表页

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        """转换为JSON字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)
