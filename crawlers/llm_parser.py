"""基于 LLM 的招标公告详情页解析器.

使用豆包模型从公告详情文本中提取结构化招标信息.
"""
import json
import re
from typing import Optional, Type

from openai import OpenAI

from .models import BidNotice


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-2-0-lite-260215"

SYSTEM_PROMPT = """你是一个专业的中国政府采购网招标公告信息提取助手。
你的任务是从给定的政府采购公告文本中，提取关键的招标/中标信息，并以严格的 JSON 格式返回。

需要提取的字段如下（如果文本中确实没有该信息，请返回 null，不要编造）：
- project_name: 采购项目名称
- category: 品目（如"货物/通用设备/计算机设备及软件/计算机网络设备"）
- purchaser_unit: 采购单位
- administrative_region: 行政区域（如"北京市"、"杭州市西湖区"）
- bid_document_time: 获取招标文件/采购文件的时间范围
- bid_document_price: 招标文件/采购文件售价（如"￥0元"、"￥500元"）
- bid_document_location: 获取招标文件/采购文件的地点
- bid_open_time: 开标时间/响应文件开启时间/投标截止时间
- bid_open_location: 开标地点/响应文件开启地点
- budget_amount: 预算金额（如"￥100.000000万元（人民币）"）
- total_bid_amount: 总中标金额/成交金额（中标公告使用）
- review_experts: 评审专家名单（中标公告使用）
- contact_person: 项目联系人
- contact_phone: 项目联系电话
- purchaser_address: 采购单位地址
- purchaser_contact: 采购单位联系方式
- agency_name: 代理机构名称
- agency_address: 代理机构地址
- agency_contact: 代理机构联系方式
- content_summary: 正文内容摘要（200字以内，概括项目主要内容和要求）
- province: 采购人所在省份（如"江西省"、"北京市"）
- city: 采购人所在城市（如"赣州市"、"成都市"）
- district: 采购人所在区/县（如"青羊区"、"铜官区"），如果是县级市则填县级市名称
- publish_time_std: 公告发布时间，严格格式化为 YYYY-MM-DD HH:MM（如"2026-05-15 16:55"），如果只到日期则输出 YYYY-MM-DD
- project_code: 项目编号（如"JXHCGC2026-GZ-J006"），如果没有填 null
- purchaser_name: 采购方名称（如"赣州市妇幼保健院"）
- purchaser_address_std: 采购方地址
- purchaser_contact_person: 采购方联系人姓名
- purchaser_contact_phone: 采购方联系方式（电话）
- agency_name_std: 代理机构名称
- agency_address_std: 代理机构地址
- agency_contact_phone: 代理机构联系方式（电话）
- project_contact_person: 项目联系人姓名
- project_contact_phone: 项目联系方式（电话）
- budget_amount_fen: 采购预算金额，精确到分，转为整数（如 797217.00元 -> 79721700），如果没有填 null
- bid_doc_start_time: 采购文件获取开始时间，格式 YYYY-MM-DD HH:MM（如"2026-05-17 00:00"）
- bid_doc_end_time: 采购文件获取截止时间，格式 YYYY-MM-DD HH:MM（如"2026-05-24 23:59"）
- response_deadline: 响应文件提交截止时间，格式 YYYY-MM-DD HH:MM
- bid_start_time: 投标开始时间（开标时间），格式 YYYY-MM-DD HH:MM
- bid_location_std: 投标地点

返回格式要求：
1. 只返回纯 JSON 对象，不要包含 markdown 代码块标记（如 ```json）
2. 不要添加任何解释性文字
3. 所有字段名必须严格使用上面列出的英文名称
4. 字符串值保持原文，不要翻译或改写
"""


def clean_html_text(html_text: str, max_length: int = 12000) -> str:
    """清理HTML文本，保留可读内容，控制长度."""
    # 去掉 script/style 标签及其内容
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    # 去掉 HTML 标签
    text = re.sub(r"<[^>]+>", "\n", text)
    # 合并多余空白和换行
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    # 去掉行首行尾空格
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)
    # 截断
    if len(text) > max_length:
        text = text[:max_length] + "\n...[内容已截断]"
    return text


class LLMParser:
    """LLM 招标信息解析器."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = 60,
        max_retries: int = 2,
    ):
        self.model = model
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    def parse(self, html: str, notice: Optional[BidNotice] = None) -> BidNotice:
        """解析详情页 HTML，返回填充好的 BidNotice.

        Args:
            html: 详情页原始 HTML
            notice: 已有的 BidNotice 实例（可选），用于复用基础字段

        Returns:
            填充好的 BidNotice 实例
        """
        if notice is None:
            notice = BidNotice()

        text = clean_html_text(html)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请从以下政府采购公告文本中提取信息：\n\n{text}\n"},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            raw_content = response.choices[0].message.content or ""
            result = self._extract_json(raw_content)
            self._apply_to_notice(result, notice)
        except Exception as e:
            print(f"[LLM解析失败] {e}")

        return notice

    def _extract_json(self, content: str) -> dict:
        """从 LLM 回复中提取 JSON 对象."""
        content = content.strip()
        # 尝试去掉 markdown 代码块
        if content.startswith("```"):
            # 找到第一个和最后一个 ```
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return json.loads(content)

    def _apply_to_notice(self, data: dict, notice: BidNotice) -> None:
        """将解析结果应用到 BidNotice 模型."""
        field_map = {
            "project_name": "project_name",
            "category": "category",
            "purchaser_unit": "purchaser_unit",
            "administrative_region": "administrative_region",
            "bid_document_time": "bid_document_time",
            "bid_document_price": "bid_document_price",
            "bid_document_location": "bid_document_location",
            "bid_open_time": "bid_open_time",
            "bid_open_location": "bid_open_location",
            "budget_amount": "budget_amount",
            "total_bid_amount": "total_bid_amount",
            "review_experts": "review_experts",
            "contact_person": "contact_person",
            "contact_phone": "contact_phone",
            "purchaser_address": "purchaser_address",
            "purchaser_contact": "purchaser_contact",
            "agency_name": "agency_name",
            "agency_address": "agency_address",
            "agency_contact": "agency_contact",
            "province": "province",
            "city": "city",
            "district": "district",
            "publish_time_std": "publish_time_std",
            "project_code": "project_code",
            "purchaser_name": "purchaser_name",
            "purchaser_address_std": "purchaser_address_std",
            "purchaser_contact_person": "purchaser_contact_person",
            "purchaser_contact_phone": "purchaser_contact_phone",
            "agency_name_std": "agency_name_std",
            "agency_address_std": "agency_address_std",
            "agency_contact_phone": "agency_contact_phone",
            "project_contact_person": "project_contact_person",
            "project_contact_phone": "project_contact_phone",
            "budget_amount_fen": "budget_amount_fen",
            "bid_doc_start_time": "bid_doc_start_time",
            "bid_doc_end_time": "bid_doc_end_time",
            "response_deadline": "response_deadline",
            "bid_start_time": "bid_start_time",
            "bid_location_std": "bid_location_std",
        }

        for json_key, model_field in field_map.items():
            value = data.get(json_key)
            if value is not None and value != "":
                setattr(notice, model_field, str(value))

        # content_summary 存入 content_text（如果 content_text 为空）
        summary = data.get("content_summary")
        if summary and not notice.content_text:
            notice.content_text = str(summary)
