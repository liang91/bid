"""中国政府采购网爬虫实现."""
import re
import time
from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin

from loguru import logger
import requests
from bs4 import BeautifulSoup

from dao import (
    ProcurementNoticeDao,
    NoticeAttachmentDao,
    NoticePackageDao,
    NoticeQualificationDao,
)
from model import _DEFAULT_DATETIME
from model.procurement_notice import ProcurementNoticeDto
from model.notice_attachment import NoticeAttachmentDto
from model.notice_package import NoticePackageDto
from model.notice_qualification import NoticeQualificationDto
from .llm_parser import LLMParser
from .parser_utils import (
    parse_amount,
    parse_chinese_datetime,
    standardize_publish_time,
    strip_html_noise,
    extract_region,
    extract_project_code,
    parse_time_range,
    parse_purchaser_contact_person,
)
from services.embedding_service import EmbeddingService

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


class CCGPCrawler:
    """中国政府采购网爬虫.

    支持爬取的栏目:
    - 地方公告 (dfgg): https://www.ccgp.gov.cn/cggg/dfgg/
    - 中央公告 (zygg): https://www.ccgp.gov.cn/cggg/zygg/
    """

    PLATFORM = "中国政府采购网"
    BASE_URL = "https://www.ccgp.gov.cn"

    PARTS = {
        "dfgg": "/cggg/dfgg/",
        "zygg": "/cggg/zygg/",
    }

    PART_NAMES = {
        "dfgg": "地方公告",
        "zygg": "中央公告",
    }

    PROMPT = """你是一个专业的政府采购网招标公告信息提取助手，你的任务是从给定的政府采购公告页HTML中，提取关键的招标信息。
需要提取的字段如下（字段名必须严格与下面列出的英文名称一致；如果文本中确实没有该信息，请返回 null，不要编造）：
    
- project_name: 采购项目名称
- project_no: 项目编号（如"JXHCGC2026-GZ-J006"）
- purchase_plan_no: 采购计划编号
- category_name: 采购品目名称（如"货物/通用设备/计算机设备及软件/计算机网络设备"）
- method: 采购方式（如"公开招标"、"竞争性谈判"、"询价"、"单一来源"）
- budget: 预算金额（如"￥100.000000万元（人民币）"）
- max_limit: 最高限价
- currency: 币种，默认为"CNY"

- region_province: 采购方所在省份（如"江西省"、"北京市"）
- region_city: 采购方所在城市（如"赣州市"、"成都市"），
- region_district: 采购方所在区/县（如"青羊区"、"铜官区"），如果是县级市则填县级市名称

- notice_date: 公告发布时间，严格格式化为 YYYY-MM-DD HH:MM（如"2026-05-15 16:55"），如果只到日期则输出 YYYY-MM-DD
- doc_obtain_start: 采购文件获取开始时间，格式 YYYY-MM-DD HH:MM。如果公告中给出的是时间范围文本（如"2026年05月17日至2026年05月24日"），可将整段文本填入此字段
- doc_obtain_end: 采购文件获取截止时间，格式 YYYY-MM-DD HH:MM
- bid_deadline: 投标截止时间/响应文件提交截止时间，格式 YYYY-MM-DD HH:MM
- bid_open_time: 开标时间，格式 YYYY-MM-DD HH:MM

- bid_platform: 投标平台/开标地点/获取招标文件的地点
- doc_price: 招标文件/采购文件售价（如"￥0元"、"￥500元"）

- purchaser_name: 采购人名称
- purchaser_address: 采购人地址
- purchaser_contact_person: 采购人联系人姓名
- purchaser_contact_phone: 采购人联系电话
- purchaser_region: 采购人所在行政区域（如"北京市"、"杭州市西湖区"）

- agency_name: 代理机构名称
- agency_address: 代理机构地址
- agency_contact_person: 代理机构联系人姓名
- agency_contact_phone: 代理机构联系电话

- project_contact_person: 项目联系人姓名
- project_contact_phone: 项目联系电话

- abstract: 正文内容摘要（300字以内，概括项目主要内容、要求、关键词，这个字段用于建全文索引）
- qualification_summary: 资质要求摘要

- notice_attachments: [ 
    {
        name: 附件名,
        url: 附件链接
    } 附件详情
] 公告附件列表

- notice_packages: [
    {
        no: 采购包编号
        name: 采购包名称,
        budge: 包预算,
        max_limit: 采购限额,
        quantity: 采购数量,
        unit: 货品单位
    }
] 采购包列表

- notice_qualifications: [
    {
        qualification_type: 资质类型,
        name: 资质/证书名称,
        required_scope: 要求范围/等级,
        valid_required: 是否要求有效期内,
        evidence_type: 证明材料类型,
        joint_bid_acceptable: 联合体是否可接受
    }
] 资质要求列表

返回格式要求：
1. 只返回纯 JSON 对象，不要包含 markdown 代码块标记（如 ```json）
2. 不要添加任何解释性文字
3. 所有字段名必须严格使用上面列出的英文名称
4. 字符串值保持原文，不要翻译或改写

你要解析的公告页HTML内容如下：

"""

    def __init__(
            self,
            part: str = "dfgg",
            delay: float = 1.0,
            max_retries: int = 3,
            timeout: int = 30,
    ):
        if part not in self.PARTS:
            raise ValueError(f"不支持的栏目: {part}，可选: {list(self.PARTS.keys())}")

        self.part = part
        self.part_path = self.PARTS[part]
        self.list_base_url = urljoin(self.BASE_URL, self.part_path)
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        self._seen_urls = set()
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _get(self, url: str) -> Optional[str]:
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code == 200:
                    return resp.text
                logger.warning(f"[HTTP {resp.status_code}] {url}")
            except requests.RequestException as e:
                logger.warning(f"[请求失败] 第{attempt}次尝试: {url} - {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt)
        return None

    def _build_list_url(self, page: int) -> str:
        if page <= 1:
            return urljoin(self.list_base_url, "index.htm")
        return urljoin(self.list_base_url, f"index_{page}.htm")

    def _parse_list_page(self, html: str, list_url: str) -> List[ProcurementNoticeDto]:
        """解析列表页，返回招标公告 DTO 列表."""
        notices = []
        soup = BeautifulSoup(html, "lxml")
        ul = soup.find("ul", class_="c_list_bid")
        if not ul:
            logger.warning(f"[解析] 未找到列表容器: {list_url}")
            return notices

        for li in ul.find_all("li"):
            a = li.find("a", href=True)
            if not a:
                continue

            dto = ProcurementNoticeDto(
                platform=self.PLATFORM,
                part=self.PART_NAMES.get(self.part, ""),
                title=a.get_text(strip=True),
                url=urljoin(list_url, a["href"]),
            )

            if em_type := li.find("em", attrs={"rel": "bxlx"}):
                dto.notice_type = em_type.get_text(strip=True)

            li_text = li.get_text(separator=" ", strip=True)
            if m := re.search(r"发布时间[：:]\s*([\d\-]{10}\s+\d{2}:\d{2})", li_text):
                dto.notice_date = parse_chinese_datetime(m.group(1).strip()) or _DEFAULT_DATETIME
            if m := re.search(r"地域[：:]\s*([^\s]+?)(?:\s+采购人|$)", li_text):
                dto.region_province = m.group(1).strip()
            if m := re.search(r"采购人[：:]\s*(.+)$", li_text):
                dto.purchaser_name = m.group(1).strip()

            notices.append(dto)

        return notices

    # -------------------------------------------------------------------------
    # 数据清洗辅助
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_notice_field(key: str, value):
        """将 LLM 或爬虫原始值清洗为 DTO 字段对应类型."""
        if value is None or value == "":
            return None
        if key in ("budget", "max_limit", "doc_price"):
            return parse_amount(str(value)) or Decimal("0.00")
        if key in ("notice_date", "doc_obtain_start", "doc_obtain_end", "bid_deadline", "bid_open_time"):
            return parse_chinese_datetime(str(value)) or _DEFAULT_DATETIME
        if key in ("joint_bid_allowed", "joint_bid_max_members", "sme_oriented", "ca_required", "status"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _build_attachment_dtos(raw_list: list) -> List[NoticeAttachmentDto]:
        result = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            result.append(NoticeAttachmentDto(
                name=str(item.get("name") or "")[:256],
                url=str(item.get("url") or "")[:512],
            ))
        return result

    @staticmethod
    def _build_package_dtos(raw_list: list) -> List[NoticePackageDto]:
        result = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            result.append(NoticePackageDto(
                no=str(item.get("no") or "")[:16],
                name=str(item.get("name") or "")[:256],
                budget=parse_amount(str(item.get("budge") or item.get("budget") or "")) or Decimal("0.00"),
                max_limit=parse_amount(str(item.get("max_limit") or "")) or Decimal("0.00"),
                quantity=Decimal(str(item.get("quantity") or "0").replace(",", "")) if item.get(
                    "quantity") else Decimal("0.0000"),
                unit=str(item.get("unit") or "")[:32],
            ))
        return result

    @staticmethod
    def _build_qualification_dtos(raw_list: list) -> List[NoticeQualificationDto]:
        from .parser_utils import to_tinyint
        result = []
        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                continue
            result.append(NoticeQualificationDto(
                qualification_type=str(item.get("qualification_type") or "")[:32],
                name=str(item.get("name") or "")[:128],
                required_scope=str(item.get("required_scope") or "")[:256],
                valid_required=to_tinyint(item.get("valid_required")),
                evidence_type=str(item.get("evidence_type") or "")[:64],
                joint_bid_acceptable=to_tinyint(item.get("joint_bid_acceptable")),
                sort_order=idx,
            ))
        return result

    # -------------------------------------------------------------------------
    # 平台相关：HTML 清理
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_html_for_llm(html: str, max_length: int = 15000) -> str:
        if not html:
            return ""

        soup = BeautifulSoup(html, "lxml")
        _NOISE_CLASSES = re.compile(
            r"header|footer|nav|menu|sidebar|breadcrumb|banner|advert|ad-|toolbar|modal|popup|dialog",
            re.IGNORECASE,
        )

        tags_to_remove = []
        for tag in soup.find_all(True):
            if not tag.name or tag.attrs is None:
                continue
            classes = " ".join(tag.get("class", []))
            tag_id = tag.get("id", "")
            if _NOISE_CLASSES.search(classes) or _NOISE_CLASSES.search(tag_id):
                if any(k in classes for k in ("vF_detail_header", "vF_detail_content", "vF_deail_maincontent")):
                    continue
                tags_to_remove.append(tag)
        for tag in tags_to_remove:
            tag.decompose()

        main_blocks = []
        selectors = [
            ("div", {"class": "vF_detail_header"}),
            ("div", {"class": "table"}),
            ("div", {"class": "vF_detail_content"}),
        ]
        for tag_name, attrs in selectors:
            block = soup.find(tag_name, attrs=attrs)
            if block:
                block.attrs = {}
                for inner in block.find_all(True):
                    inner.attrs = {}
                main_blocks.append(str(block))

        if main_blocks:
            result = "\n".join(main_blocks)
        else:
            body = soup.find("body")
            root = body if body else soup
            for tag in root.find_all(True):
                tag.attrs = {}
            result = str(root)

        if len(result) > max_length:
            result = result[:max_length] + "\n<!-- 内容已截断 -->"

        return result

    # -------------------------------------------------------------------------
    # 平台相关：LLM 结果填充与后处理
    # -------------------------------------------------------------------------

    @staticmethod
    def _enrich_notice(dto: ProcurementNoticeDto) -> None:
        """从已有字段中提取并标准化各类信息."""
        # 省市区
        dto.region_province, dto.region_city, dto.region_district = extract_region(
            address=dto.purchaser_address,
            region=dto.region_province,
            administrative_region=dto.purchaser_region,
        )

        # 公告发布时间标准化
        if dto.notice_date and dto.notice_date != _DEFAULT_DATETIME:
            _std = standardize_publish_time(str(dto.notice_date))
            if _std:
                dto.notice_date = parse_chinese_datetime(_std) or dto.notice_date

        # 项目编号
        dto.project_no = extract_project_code(dto.abstract, dto.project_name)

        # 采购方联系人
        if not dto.purchaser_contact_person:
            dto.purchaser_contact_person = parse_purchaser_contact_person(dto.abstract)

        # 采购文件获取时间拆分
        if dto.doc_obtain_start and dto.doc_obtain_start != _DEFAULT_DATETIME:
            start_str = str(dto.doc_obtain_start)
            if "至" in start_str or "到" in start_str:
                start, end = parse_time_range(start_str)
                if start:
                    dto.doc_obtain_start = parse_chinese_datetime(start) or dto.doc_obtain_start
                if end:
                    dto.doc_obtain_end = parse_chinese_datetime(end) or dto.doc_obtain_end

        # 投标截止时间 / 开标时间标准化
        if dto.bid_open_time and dto.bid_open_time != _DEFAULT_DATETIME:
            _std = standardize_publish_time(str(dto.bid_open_time))
            if _std:
                dto.bid_open_time = parse_chinese_datetime(_std) or dto.bid_open_time
            if not dto.bid_deadline or dto.bid_deadline == _DEFAULT_DATETIME:
                dto.bid_deadline = dto.bid_open_time

    @staticmethod
    def _is_tender_notice(dto: ProcurementNoticeDto) -> bool:
        if not dto.notice_type:
            return False
        nt = dto.notice_type.strip()
        if "招标" not in nt:
            return False
        exclude_keywords = ("中标", "成交", "结果", "更正", "废标", "终止")
        if any(kw in nt for kw in exclude_keywords):
            return False
        return True

    # ========================================================================
    # 第1步：fetch_list
    # ========================================================================
    def fetch_list(self, pages: int = 1) -> dict:
        all_notices = []
        for page in range(1, pages + 1):
            url = self._build_list_url(page)
            html = self._get(url)
            if not html:
                continue

            notices = self._parse_list_page(html, url)
            all_notices.extend(notices)
            logger.info(f"[fetch_list] 第{page}页 获取 {len(notices)} 条，累计 {len(all_notices)} 条")
            time.sleep(self.delay)

        tender_notices = [dto for dto in all_notices if self._is_tender_notice(dto)]
        excluded = len(all_notices) - len(tender_notices)
        if excluded > 0:
            logger.info(f"[fetch_list] 排除非招标公告 {excluded} 条，保留 {len(tender_notices)} 条")

        if tender_notices:
            ProcurementNoticeDao().save(tender_notices)
            logger.info(f"[fetch_list] 入库完成: 新增 {len(tender_notices)} 条")
            return {
                "crawled": len(all_notices),
                "inserted": len(tender_notices),
            }

        return {"crawled": len(all_notices), "inserted": 0}

    # ========================================================================
    # 第2步：fetch_html
    # ========================================================================

    def fetch_html(self, limit: int = 100) -> dict:
        notices = ProcurementNoticeDao().fetch_by_status(status=1, platform=self.PLATFORM, limit=limit)
        if not notices:
            logger.info("[fetch_html] 没有待获取 HTML 的记录")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"[fetch_html] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, dto in enumerate(notices, 1):
            time.sleep(self.delay)
            html = self._get(dto.url)
            if html:
                filtered_html = strip_html_noise(html)
                ok = ProcurementNoticeDao().update_html(dto.id, filtered_html)
                if ok:
                    success += 1
                    logger.info(f"[fetch_html] {idx}/{len(notices)} 成功: {dto.project_name[:40]}...")
                else:
                    failed += 1
                    logger.error(f"[fetch_html] {idx}/{len(notices)} 更新DB失败: {dto.url}")
            else:
                failed += 1
                logger.error(f"[fetch_html] {idx}/{len(notices)} 请求失败: {dto.url}")

        logger.info(f"[fetch_html] 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"total": len(notices), "success": success, "failed": failed}

    # ========================================================================
    # 第3步：parse_detail
    # ========================================================================

    def parse_detail(self, limit: int = 100) -> dict:
        notices = ProcurementNoticeDao().fetch_by_status(status=20, platform=self.PLATFORM, limit=limit)
        if not notices:
            logger.info("[parse_detail] 没有待解析的记录")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"[parse_detail] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, dto in enumerate(notices, 1):
            html = dto.html
            if not html:
                logger.warning(f"[parse_detail] {idx}/{len(notices)} 跳过: 无HTML内容")
                failed += 1
                continue

            try:
                cleaned_text = self._clean_html_for_llm(html)
                llm_result = LLMParser.parse(CCGPCrawler.PROMPT + cleaned_text)

                sub_attachments = llm_result.pop("notice_attachments", None) or []
                sub_packages = llm_result.pop("notice_packages", None) or []
                sub_qualifications = llm_result.pop("notice_qualifications", None) or []

                # 用清洗后的值更新 DTO
                dto_dict = dto.model_dump()
                for key, value in llm_result.items():
                    if value is not None and value != "":
                        dto_dict[key] = self._clean_notice_field(key, value)
                dto = ProcurementNoticeDto(**dto_dict)

                self._enrich_notice(dto)
                dto.status = 30
                ok = ProcurementNoticeDao().update_parsed(dto)
                if ok:
                    NoticeAttachmentDao().insert(dto.id, self._build_attachment_dtos(sub_attachments))
                    NoticePackageDao().insert(dto.id, self._build_package_dtos(sub_packages))
                    NoticeQualificationDao().insert(dto.id, self._build_qualification_dtos(sub_qualifications))

                    try:
                        embedding = EmbeddingService.get_notice_embedding(dto)
                        if embedding:
                            ProcurementNoticeDao().update_embedding(dto.id, embedding)
                            logger.info(f"[parse_detail-embedding] {idx}/{len(notices)} 成功: id={dto.id}")
                        else:
                            logger.warning(f"[parse_detail-embedding] {idx}/{len(notices)} 返回空: id={dto.id}")
                    except Exception as e:
                        logger.warning(f"[parse_detail-embedding] {idx}/{len(notices)} 失败: id={dto.id}, {e}")

                    success += 1
                    logger.info(f"[parse_detail-llm] {idx}/{len(notices)} 成功: {dto.project_name[:40]}...")
                else:
                    failed += 1
                    logger.error(f"[parse_detail] {idx}/{len(notices)} 更新DB失败: id={dto.id}")
            except Exception as e:
                failed += 1
                logger.error(f"[parse_detail] {idx}/{len(notices)} 解析失败: {e}")

            break

        logger.info(f"[parse_detail] 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"total": len(notices), "success": success, "failed": failed}

    # ========================================================================
    # 兼容方法：一键运行
    # ========================================================================

    def run(self, pages: Optional[int] = 1) -> dict:
        logger.info("=" * 60)
        logger.info(f"[run] 开始三步流程 - 栏目: {self.part}")
        logger.info("=" * 60)

        list_stats = self.fetch_list(pages=pages)
        html_stats = self.fetch_html(limit=9999)
        parse_stats = self.parse_detail(limit=9999)

        logger.info("=" * 60)
        logger.info("[run] 三步流程全部完成")
        logger.info(f"  fetch_list : 插入 {list_stats.get('inserted', 0)} 条")
        logger.info(f"  fetch_html : 成功 {html_stats.get('success', 0)} 条")
        logger.info(f"  parse_detail: 成功 {parse_stats.get('success', 0)} 条")
        logger.info("=" * 60)
        return {
            "fetch_list": list_stats,
            "fetch_html": html_stats,
            "parse_detail": parse_stats,
        }
