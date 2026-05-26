"""中国政府采购网爬虫实现."""
import os
import re
import time
from decimal import Decimal
from typing import List, Optional
from urllib.parse import urljoin

from loguru import logger
import requests
from bs4 import BeautifulSoup, Comment

from dao import (
    ProcurementNoticeDao,
    NoticeAttachmentDao,
    NoticePackageDao,
    NoticeQualificationDao,
)
from model.procurement_notice import ProcurementNoticeDto
from model.notice_attachment import NoticeAttachmentDto
from model.notice_package import NoticePackageDto
from model.notice_qualification import NoticeQualificationDto
from crawlers.llm_parser import LLMParser

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
需要提取的字段如下（字段名必须严格与下面列出的英文名称一致；如果文本中确实没有该信息，不要编造）：
    
- project_name: 采购项目名称
- project_no: 项目编号（如"JXHCGC2026-GZ-J006"）
- purchase_plan_no: 采购计划编号
- method: 采购方式（如"公开招标"、"竞争性谈判"、"询价"、"单一来源"）
- budget: 预算金额
- currency: 币种，默认为"CNY"
- joint_bid_allowed: 是否允许联合投标: 0-不允许 1-允许 整数类型，默认值：0
- join_bid_max_members: 联合投标最多参与方数量，整数类型，默认值：1
- sme_oriented: 是否专门面向中小企业: 0-不是 1-是，整数类型，默认值：0

- region_province: 采购方所在省份 如:"江西"、"北京"、"香港","新疆"（省级自治区用省名，比如：新疆维吾尔自治区对应新疆）
- region_city: 采购方所在城市 如:"赣州"、"成都"，
- region_district: 采购方所在区/县（如:"新安县","青羊区"、"铜官区"），如果是县级市则填县级市名称

- notice_date: 公告发布时间，严格格式化为 YYYY-MM-DD HH:MM（如"2026-05-15 16:55"），如果只到日期则输出 YYYY-MM-DD
- doc_obtain_start: 采购文件获取开始时间，格式 YYYY-MM-DD HH:MM
- doc_obtain_end: 采购文件获取截止时间，格式 YYYY-MM-DD HH:MM
- bid_deadline: 投标截止时间/响应文件提交截止时间，格式 YYYY-MM-DD HH:MM
- bid_open_time: 开标时间，格式 YYYY-MM-DD HH:MM

- bid_platform: 投标平台/开标地点/获取招标文件的地点
- doc_price: 招标文件费用

- purchaser_name: 采购人名称
- purchaser_address: 采购人地址
- purchaser_contact_person: 采购人联系人姓名
- purchaser_contact_phone: 采购人联系电话
- agency_name: 代理机构名称
- agency_address: 代理机构地址
- agency_contact_person: 代理机构联系人姓名
- agency_contact_phone: 代理机构联系电话

- project_contact_person: 项目联系人姓名
- project_contact_phone: 项目联系电话

- qualification_summary: 申请方/供应商资质要求摘要
- industry_tags: [
    "行业大类标签",
    "行业细分标签1",
    "行业细分标签2",
    "行业细分标签3"
] 所需供应商的行业标签（字符串列表类型）

- abstract: 公告内容摘要，500字以内
- supplier_profile: 所需供应商的画像，要包含：供应商需要在哪些行业（行业大类标签、行业细分标签）、所需的资质/证书、供应商要具备能力等，300字以内，备注：这个字段会用于和供应商信息做语义匹配，用于筛选符合招标要求的供应商

- notice_attachments: [ 
    {
        name: 附件名,
        url: 附件链接
    } 附件详情
] 公告附件列表

- notice_packages: [
    {
        no: 采购包编号,
        name: 采购包名称,
        budget: 包预算,
        quantity: 采购数量(字符串类型，默认值是空字符串),
        unit: 货品单位(字符串类型，默认值是空字符串),
        intro: 标项规格描述或概况介绍
    }
] 采购包列表

- notice_qualifications: [
    {
        qualification_type: 资质类型,
        name: 资质/证书名称
    }
] 供应商/申请方资质要求列表

返回格式要求：
1. 只返回纯 JSON 对象，不要包含 markdown 代码块标记（如 ```json）
2. 不要添加任何解释性文字
3. 所有字段名必须严格使用上面列出的英文名称
4. 字符串值保持原文，不要翻译或改写
5. 预算或费用金额统一换算成元，字符串格式，最多保留两位非0小数，如果都是0，不保留小数位

你要解析的公告页HTML内容如下：

"""

    def __init__(
            self,
            part: str = "dfgg",
            delay: float = 1.0,
            max_retries: int = 3,
    ):
        if part not in self.PARTS:
            raise ValueError(f"不支持的栏目: {part}，可选: {list(self.PARTS.keys())}")

        self.part = part
        self.part_path = self.PARTS[part]
        self.list_base_url = urljoin(self.BASE_URL, self.part_path)
        self.delay = delay
        self.max_retries = max_retries
        self._seen_urls = set()
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _get(self, url: str) -> Optional[str]:
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=30)
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

            notices.append(dto)

        return notices

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

    @staticmethod
    def save_cleaned_html(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        main = soup.find('div', class_='vF_deail_maincontent')
        # 去掉js/css代码
        for tag in main.find_all(['script', 'style']):
            tag.decompose()
        # 去掉评论
        for comment in main.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        # 去掉标签属性
        for tag in main.find_all():
            tag.attrs = {k: v for k, v in tag.attrs.items() if k == 'href'}
        content = str(main)
        content = content.replace("<span>", "").replace("</span>", "")
        os.makedirs("html", exist_ok=True)
        filename = f"html/{int(time.time() * 1000000)}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return filename

    @staticmethod
    def get_cleand_html(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

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
            ProcurementNoticeDao.create(tender_notices)
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
        notices = ProcurementNoticeDao.fetch_by_status(status=1, platform=self.PLATFORM, limit=limit)
        if not notices:
            logger.info("[fetch_html] 没有待获取 HTML 的记录")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"[fetch_html] 共 {len(notices)} 条待处理")
        success = failed = 0

        for notice in notices:
            html = self._get(notice.url)
            if html:
                html_path = self.save_cleaned_html(html)
                ProcurementNoticeDao.update_html(notice.id, html_path)
                success += 1
                time.sleep(self.delay)
            else:
                failed += 1

        logger.info(f"[fetch_html] 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"total": len(notices), "success": success, "failed": failed}

    # ========================================================================
    # 第3步：parse_detail
    # ========================================================================
    def parse_detail(self, limit: int = 100) -> dict:
        notices = ProcurementNoticeDao.fetch_by_status(status=20, platform=self.PLATFORM, limit=limit)
        if not notices:
            logger.info("[parse_detail] 没有待解析的记录")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"[parse_detail] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, notice in enumerate(notices, 1):
            if not notice.html:
                logger.warning(f"[parse_detail] {idx}/{len(notices)} 跳过: 无HTML内容")
                failed += 1
                continue

            try:
                data = LLMParser.parse(CCGPCrawler.PROMPT + self.get_cleand_html(notice.html))
                attachments = data.pop("notice_attachments", None) or []
                attachments = [NoticeAttachmentDto(**attachment) for attachment in attachments]

                packages = data.pop("notice_packages", None) or []
                packages = [NoticePackageDto(**package) for package in packages]

                qualifications = data.pop("notice_qualifications", None) or []
                qualifications = [NoticeQualificationDto(**qualification) for qualification in qualifications]

                notice_dict = notice.model_dump()
                notice_dict.update(data)
                notice = ProcurementNoticeDto(**notice_dict)
                notice.supplier_profile_embedding = EmbeddingService.embed(notice.supplier_profile, as_bytes=True)
                ok = ProcurementNoticeDao.update_parsed(notice)
                if ok:
                    NoticeAttachmentDao.insert(notice.id, attachments)
                    NoticePackageDao.insert(notice.id, packages)
                    NoticeQualificationDao.insert(notice.id, qualifications)
                    success += 1
                    logger.info(f"[parse_detail-llm] {idx}/{len(notices)} 成功: {notice.project_name[:40]}...")
                else:
                    failed += 1
                    logger.error(f"[parse_detail] {idx}/{len(notices)} 更新DB失败: id={notice.id}")
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
