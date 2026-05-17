"""数据模型定义.

所有模型类与 bid_database.sql 中的表一一对应.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from typing import Optional


# ---------------------------------------------------------------------------
# 招标公告主表
# ---------------------------------------------------------------------------

@dataclass
class ProcurementNotice:
    """招标公告数据模型，字段与 procurement_notices 表一一对应."""

    # === 数据库主键 ===
    id: int = 0                               # 数据库自增ID

    # === 来源信息 ===
    platform: str = ""                        # 平台：中国政府采购网
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
    joint_bid_max_members: int = 0            # 联合体最多成员数
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
    abstract: str = ""                        # 原文摘要（包含关键词，此字段用于全文检索）
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


# ---------------------------------------------------------------------------
# 公告资质要求表
# ---------------------------------------------------------------------------

@dataclass
class NoticeQualification:
    """招标公告资质要求明细，对应 notice_qualifications 表."""

    id: int = 0
    notice_id: int = 0                        # 关联公告ID
    qualification_type: str = ""              # 资质类型：资质许可/业绩要求/人员要求/设备要求/其他
    name: str = ""                            # 资质名称
    required_scope: str = ""                  # 要求范围/等级
    valid_required: int = 1                   # 是否要求有效期内
    evidence_type: str = ""                   # 证明材料类型
    joint_bid_acceptable: int = 0             # 联合体是否可接受
    sort_order: int = 0                       # 排序
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)


# ---------------------------------------------------------------------------
# 公告附件表
# ---------------------------------------------------------------------------

@dataclass
class NoticeAttachment:
    """招标公告附件，对应 notice_attachments 表."""

    id: int = 0
    notice_id: int = 0                        # 关联公告ID
    name: str = ""                            # 附件名称
    url: str = ""                             # 原始下载链接
    object_key: str = ""                      # 对象存储Key
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)


# ---------------------------------------------------------------------------
# 公告分包表
# ---------------------------------------------------------------------------

@dataclass
class NoticePackage:
    """招标公告分包信息，对应 notice_packages 表."""

    id: int = 0
    notice_id: int = 0                        # 关联公告ID
    no: str = ""                              # 包号
    name: str = ""                            # 包名称
    budget: str = ""                          # 包预算
    max_limit: str = ""                       # 包最高限价
    quantity: str = ""                        # 数量
    unit: str = ""                            # 单位
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)


# ---------------------------------------------------------------------------
# 供应商画像表
# ---------------------------------------------------------------------------

@dataclass
class SupplierProfile:
    """供应商画像，对应 supplier_profiles 表."""

    id: int = 0
    user_id: int = 0                          # 用户ID

    # === 公司基本信息 ===
    company_name: str = ""                    # 公司名称
    company_scale: str = ""                   # 企业规模：微型/小型/中型/大型
    province: str = ""                        # 公司所在省
    city: str = ""                            # 公司所在市
    district: str = ""                        # 公司所在区

    # === 业务范围 ===
    business_scope: str = ""                  # 业务范围关键词，逗号分隔

    # === 资质证书 ===
    qualifications: list = field(default_factory=list)  # 资质证书列表 [{name, cert_no, valid_until}]
    qualification_summary: str = ""           # 资质摘要，用于快速匹配

    # === 需求偏好 ===
    min_budget: str = ""                      # 最低预算偏好（0表示不限）
    max_budget: str = "999999999.99"          # 最高预算偏好
    preferred_regions: str = ""               # 偏好地区，逗号分隔
    preferred_methods: str = ""               # 偏好采购方式，逗号分隔

    # === 服务范围 ===
    service_regions: str = ""                 # 可服务地区，逗号分隔
    joint_bid_willing: int = 0                # 是否愿意联合体投标

    # === 排除项 ===
    excluded_keywords: str = ""               # 排除关键词，逗号分隔

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)


# ---------------------------------------------------------------------------
# 匹配结果表
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    """供应商-招标公告匹配结果，对应 match_results 表."""

    id: int = 0

    # === 关联信息 ===
    supplier_id: int = 0                      # 供应商ID（对应 supplier_profiles.user_id）
    notice_id: int = 0                        # 公告ID（对应 procurement_notices.id）

    # === AI 精筛结果 ===
    ai_match_score: str = ""                  # AI匹配分数（0-100）
    ai_match_level: str = ""                  # AI匹配等级：高(>=80)/中(60-79)/低(<60)/不匹配
    ai_match_reasons: str = ""                # AI给出的匹配理由
    ai_risk_tips: str = ""                    # AI给出的风险提示
    ai_key_matching_points: str = ""          # AI提取的关键匹配点
    ai_mismatch_points: str = ""              # AI提取的不匹配点
    ai_recommendation: str = ""               # AI建议：强烈推荐/推荐/谨慎考虑/不推荐
    ai_raw_response: str = ""                 # AI原始返回内容（用于调试和追溯）
    ai_call_time: str = ""                    # AI调用时间

    # === 最终排序与输出 ===
    final_score: str = ""                     # 最终排序分数
    final_rank: int = 0                       # 该供应商所有匹配中的排名
    is_top3: int = 0                          # 是否进入Top3推荐

    # === 推送状态 ===
    push_status: int = 0                      # 0未推送 1已推送 2推送失败 3用户已读 4用户忽略
    push_time: str = ""                       # 推送时间
    push_channel: str = ""                    # 推送渠道
    push_message_id: str = ""                 # 企业微信消息ID

    # === 用户反馈 ===
    user_feedback_score: int = 0              # 用户反馈评分：0未反馈 1-5星
    user_feedback_comment: str = ""           # 用户反馈文字
    user_viewed: int = 0                      # 用户是否点击查看详情
    user_favorite: int = 0                    # 用户是否收藏
    user_applied: int = 0                     # 用户是否实际投标
    user_feedback_time: str = ""              # 用户反馈时间

    # === 状态 ===
    status: int = 1                           # 1有效 2已过期 3已删除

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)
