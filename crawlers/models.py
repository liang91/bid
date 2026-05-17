"""数据模型定义."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


@dataclass
class ProcurementNotice:
    """招标公告数据模型，字段与 procurement_notices 表一一对应."""

    # === 数据库主键 ===
    id: int = 0                               # 数据库自增ID

    # === 来源信息 ===
    platform: str = ""                        # 平台
    part: str = ""                            # 爬取栏目：中央公告/地方公告
    title: str = ""                           # 列表页原始标题

    # === 核心信息 ===
    notice_type: str = ""                     # 公告类型
    url: str = ""                             # 来源URL

    # === 地区 ===
    region_province: str = ""                 # 省/自治区/直辖市
    region_city: str = ""                     # 市/直辖市辖区
    region_district: str = ""                 # 区/县

    # === 项目信息 ===
    project_name: str = ""                    # 项目名称
    project_no: str = ""                      # 项目编号
    purchase_plan_no: str = ""                # 采购计划编号

    # === 金额（原始字符串，入库时由 db_storage 转换为 Decimal） ===
    budget: str = ""                          # 预算金额
    max_limit: str = ""                       # 最高限价
    currency: str = "CNY"                     # 币种

    # === 品目 ===
    category_code: str = ""                   # 采购品目编码
    category_name: str = ""                   # 采购品目名称

    # === 采购方式 ===
    method: str = ""                          # 公开招标/竞争性谈判/询价/单一来源
    joint_bid_allowed: int = 0                # 是否接受联合体
    joint_bid_max_members: int = 1            # 联合体最多成员数
    sme_oriented: int = 0                     # 是否面向中小企业

    # === 时间节点（原始字符串，入库时由 db_storage 转换为 datetime） ===
    notice_date: str = ""                     # 公告发布日期
    doc_obtain_start: str = ""                # 文件获取开始
    doc_obtain_end: str = ""                  # 文件获取截止
    bid_deadline: str = ""                    # 投标截止
    bid_open_time: str = ""                   # 开标时间

    # === 投标方式 ===
    bid_platform: str = ""                    # 投标平台
    bid_platform_url: str = ""                # 投标平台URL
    ca_required: int = 0                      # 是否需要CA证书
    doc_price: str = ""                       # 标书费用

    # === 采购方（采购人）信息 ===
    purchaser_name: str = ""                  # 采购人名称
    purchaser_address: str = ""               # 采购人地址
    purchaser_contact_person: str = ""        # 采购人联系人
    purchaser_contact_phone: str = ""         # 采购人联系电话
    purchaser_region: str = ""                # 采购人地区

    # === 代理机构信息 ===
    agency_name: str = ""                     # 代理机构名称
    agency_address: str = ""                  # 代理机构地址
    agency_contact_person: str = ""           # 代理机构联系人
    agency_contact_phone: str = ""            # 代理机构联系电话
    agency_region: str = ""                   # 代理机构地区

    # === 项目联系人信息 ===
    project_contact_person: str = ""          # 项目联系人
    project_contact_phone: str = ""           # 项目联系方式

    # === 匹配特征 ===
    qualification_summary: str = ""           # 资质要求摘要
    industry_tags: list = field(default_factory=list)      # 行业标签
    keywords: list = field(default_factory=list)             # 关键词
    suggested_company_types: list = field(default_factory=list)  # 建议供应商类型
    geographic_advantage: str = ""            # 地域优势

    # === 原始摘要 ===
    raw_abstract: str = ""                    # 原文摘要
    html: str = ""                            # 详情页原始HTML
    parse_time: str = ""                      # 解析时间

    # === 状态（爬取流程状态） ===
    status: int = 1                           # 1:获取概要信息 20:获取了网页内容 30:解析出了公告内容
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    # ---------------------------------------------------------
    # 以下为爬虫辅助字段（非数据库字段，用于解析中间状态/溯源）
    # ---------------------------------------------------------
    attachments: list = field(default_factory=list)  # 附件列表

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        """转换为JSON字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)
