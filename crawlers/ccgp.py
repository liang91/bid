"""中国政府采购网爬虫实现."""
import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from dao import *
from model import ProcurementNotice
from .llm_parser import LLMParser
from .parser_utils import strip_html_noise

logger = logging.getLogger(__name__)

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

    # 栏目映射
    PARTS = {
        "dfgg": "/cggg/dfgg/",  # 地方公告
        "zygg": "/cggg/zygg/",  # 中央公告
    }

    # 栏目中文名称
    PART_NAMES = {
        "dfgg": "地方公告",
        "zygg": "中央公告",
    }

    # -------------------------------------------------------------------------
    # 平台相关：LLM 解析配置
    # -------------------------------------------------------------------------
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
        """初始化爬虫.

        Args:
            part: 栏目代码，'dfgg'(地方公告) 或 'zygg'(中央公告)
            delay: 请求间隔（秒）
            max_retries: 最大重试次数
            timeout: 请求超时时间
        """
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
        """发送GET请求并返回HTML文本，带重试机制."""
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
        """构建列表页URL.

        第1页: index.htm
        第2页+: index_2.htm, index_3.htm ...
        """
        if page <= 1:
            return urljoin(self.list_base_url, "index.htm")
        return urljoin(self.list_base_url, f"index_{page}.htm")

    def _parse_list_page(self, html: str, list_url: str) -> List[ProcurementNotice]:
        """解析列表页，返回招标公告列表."""
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

            notice = ProcurementNotice()
            notice.platform = CCGPCrawler.PLATFORM
            notice.part = CCGPCrawler.PART_NAMES.get(self.part, "")
            notice.title = a.get_text(strip=True)
            notice.url = urljoin(list_url, a["href"])

            # 提取 <em rel="bxlx"> 公告类型
            if em_type := li.find("em", attrs={"rel": "bxlx"}):
                notice.notice_type = em_type.get_text(strip=True)

            # 使用正则从整个 li 文本中提取字段（更可靠）
            li_text = li.get_text(separator=" ", strip=True)
            # 发布时间：2026-05-14 15:30
            if m := re.search(r"发布时间[：:]\s*([\d\-]{10}\s+\d{2}:\d{2})", li_text):
                notice.notice_date = m.group(1).strip()
            # 地域：xxx（注意地域可能为空）
            if m := re.search(r"地域[：:]\s*([^\s]+?)(?:\s+采购人|$)", li_text):
                notice.region_province = m.group(1).strip()
            # 采购人：xxx（通常是最后一部分）
            if m := re.search(r"采购人[：:]\s*(.+)$", li_text):
                notice.purchaser_name = m.group(1).strip()

            notices.append(notice)

        return notices

    # -------------------------------------------------------------------------
    # 平台相关：HTML 清理（针对中国政府采购网详情页结构）
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_html_for_llm(html: str, max_length: int = 15000) -> str:
        """清理 HTML，提取正文并保留标签结构供 LLM 解析.

        注意：入参 html 是 fetch_html 阶段经过 strip_html_noise 过滤后的 body 内容
       （已去除 head/script/style/nav/footer 等标签），本方法在此基础上：
        - 移除 class/id 包含噪声关键词的 div（如顶部导航栏 v4incheadertop、
          面包屑 vF_deail_currentloc、底部版权 footer、相关公告 vF_detail_relcontent）
        - 优先提取 vF_detail_header（标题）、.table（概要表格）、vF_detail_content（正文）
        - 去掉所有标签的属性（class、id、style 等），但保留 HTML 标签本身，
          使 LLM 能借助表格、段落等结构更好地解析信息
        - 控制总长度
        """
        if not html:
            return ""

        soup = BeautifulSoup(html, "lxml")

        _NOISE_CLASSES = re.compile(
            r"header|footer|nav|menu|sidebar|breadcrumb|banner|advert|ad-|toolbar|modal|popup|dialog",
            re.IGNORECASE,
        )

        # 1. 去掉带有噪声 class/id 的标签
        # 注意：先收集再统一 decompose，避免在迭代 find_all(True) 时修改树结构
        # 导致 lxml 产生 name=''、attrs=None 的幽灵节点
        tags_to_remove = []
        for tag in soup.find_all(True):
            # 防御：跳过 lxml 可能产生的空节点
            if not tag.name or tag.attrs is None:
                continue
            classes = " ".join(tag.get("class", []))
            tag_id = tag.get("id", "")
            if _NOISE_CLASSES.search(classes) or _NOISE_CLASSES.search(tag_id):
                # 保护本平台主要内容区域，避免误删
                if any(k in classes for k in ("vF_detail_header", "vF_detail_content", "vF_deail_maincontent")):
                    continue
                tags_to_remove.append(tag)
        for tag in tags_to_remove:
            tag.decompose()

        # 2. 提取主要内容区域，去掉所有标签的属性但保留标签
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
            # fallback：简化整个 body，去掉所有属性保留标签
            body = soup.find("body")
            root = body if body else soup
            for tag in root.find_all(True):
                tag.attrs = {}
            result = str(root)

        # 3. 截断
        if len(result) > max_length:
            result = result[:max_length] + "\n<!-- 内容已截断 -->"

        return result

    # -------------------------------------------------------------------------
    # 平台相关：LLM 结果填充与后处理
    # -------------------------------------------------------------------------

    @staticmethod
    def _enrich_notice(notice: ProcurementNotice) -> None:
        """从已有字段中提取并标准化各类信息."""
        from .parser_utils import (
            extract_region,
            standardize_publish_time,
            extract_project_code,
            parse_time_range,
            parse_purchaser_contact_person,
        )

        # 省市区
        notice.region_province, notice.region_city, notice.region_district = extract_region(
            address=notice.purchaser_address,
            region=notice.region_province,
            administrative_region=notice.purchaser_region,
        )

        # 公告发布时间标准化
        if notice.notice_date:
            notice.notice_date = standardize_publish_time(notice.notice_date)

        # 项目编号
        notice.project_no = extract_project_code(notice.abstract, notice.project_name)

        # 采购方联系人（从正文尽力提取，如果表格中未提供）
        if not notice.purchaser_contact_person:
            notice.purchaser_contact_person = parse_purchaser_contact_person(notice.abstract)

        # 采购文件获取时间拆分：只有当 doc_obtain_start 是时间范围文本时才拆分
        if notice.doc_obtain_start and (
            "至" in notice.doc_obtain_start or "到" in notice.doc_obtain_start
        ):
            notice.doc_obtain_start, notice.doc_obtain_end = parse_time_range(notice.doc_obtain_start)

        # 投标截止时间 / 开标时间标准化
        if notice.bid_open_time:
            _std = standardize_publish_time(notice.bid_open_time)
            notice.bid_open_time = _std
            # 只有当 bid_deadline 为空时，才用 bid_open_time 回填
            if not notice.bid_deadline:
                notice.bid_deadline = _std

    @staticmethod
    def _is_tender_notice(notice: ProcurementNotice) -> bool:
        """判断公告是否为"招标公告"类型（采购类公告，非结果类）.

        notice_type 包含"招标"即认为是采购类招标公告，
        排除中标、成交、结果、更正、废标、终止等结果类公告。
        """
        if not notice.notice_type:
            return False
        nt = notice.notice_type.strip()
        # 必须包含"招标"
        if "招标" not in nt:
            return False
        # 排除结果/成交类公告
        exclude_keywords = ("中标", "成交", "结果", "更正", "废标", "终止")
        if any(kw in nt for kw in exclude_keywords):
            return False
        return True

    # ========================================================================
    # 第1步：fetch_list —— 爬取公告列表，保存概要信息（status=1）
    # ========================================================================

    def fetch_list(
            self,
            pages: Optional[int] = None,
    ) -> dict:
        """爬取列表页，过滤并保存"招标公告"到数据库.

        Args:
            pages: 指定爬取页数，None 则爬取全部

        Returns:
            {"crawled": int, "filtered": int, "inserted": int, "skipped": int}
        """
        all_notices = []
        # 解析列表页各页
        for page in range(1, pages + 1):
            url = self._build_list_url(page)
            html = self._get(url)
            if not html:
                if pages is None:
                    break  # 未指定页数时，请求失败视为已到末尾
                continue

            notices = self._parse_list_page(html, url)
            all_notices.extend(notices)
            logger.info(f"[fetch_list] 第{page}页 获取 {len(notices)} 条，累计 {len(all_notices)} 条")

            if not notices and pages is None:
                break  # 未指定页数时，无数据视为已到末尾
            time.sleep(self.delay)

        # 去重（基于 URL）
        unique_notices = []
        for n in all_notices:
            if n.url not in self._seen_urls:
                self._seen_urls.add(n.url)
                unique_notices.append(n)
        all_notices = unique_notices
        logger.info(f"[fetch_list] 去重后共 {len(all_notices)} 条")

        # 过滤：仅保留"招标公告"类型
        tender_notices = [n for n in all_notices if self._is_tender_notice(n)]
        excluded = len(all_notices) - len(tender_notices)
        if excluded > 0:
            logger.info(f"[fetch_list] 排除非招标公告 {excluded} 条，保留 {len(tender_notices)} 条")

        # 存入数据库（INSERT IGNORE，跳过已存在的 URL）
        if tender_notices:
            stats = ProcurementNoticeDao.instance().insert_list(tender_notices)
            logger.info(
                f"[fetch_list] 入库完成: 新增 {stats['inserted']} 条, "
                f"跳过已存在 {stats['skipped']} 条"
            )
            return {
                "crawled": len(all_notices) + excluded,
                "filtered": len(tender_notices),
                "inserted": stats["inserted"],
                "skipped": stats["skipped"],
            }

        return {"crawled": len(all_notices), "filtered": 0, "inserted": 0, "skipped": 0}

    # ========================================================================
    # 第2步：fetch_html —— 获取详情页原始 HTML（status=1 → 20）
    # ========================================================================

    def fetch_html(self, limit: int = 100) -> dict:
        """从数据库读取 status=1 的记录，获取详情页 HTML 并存回数据库.

        Args:
            limit: 每次处理的最大条数

        Returns:
            {"total": int, "success": int, "failed": int}
        """
        notices = ProcurementNoticeDao.instance().fetch_by_status(status=1, platform=self.PLATFORM, limit=limit)
        if not notices:
            logger.info("[fetch_html] 没有待获取 HTML 的记录")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"[fetch_html] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, notice in enumerate(notices, 1):
            time.sleep(self.delay)
            html = self._get(notice.url)
            if html:
                # 去掉 head/foot/css/js 等噪声标签，保留正文 HTML 结构
                filtered_html = strip_html_noise(html)
                ok = ProcurementNoticeDao.instance().update_html(notice.id, filtered_html)
                if ok:
                    success += 1
                    logger.info(f"[fetch_html] {idx}/{len(notices)} 成功: {notice.project_name[:40]}...")
                else:
                    failed += 1
                    logger.error(f"[fetch_html] {idx}/{len(notices)} 更新DB失败: {notice.url}")
            else:
                failed += 1
                logger.error(f"[fetch_html] {idx}/{len(notices)} 请求失败: {notice.url}")

        logger.info(f"[fetch_html] 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"total": len(notices), "success": success, "failed": failed}

    # ========================================================================
    # 第3步：parse_detail —— LLM 解析详情页（status=20 → 30）
    # ========================================================================

    def parse_detail(self, limit: int = 100) -> dict:
        """从数据库读取 status=20 的记录，调用 LLM 解析并更新结构化字段.

        Args:
            limit: 每次处理的最大条数

        Returns:
            {"total": int, "success": int, "failed": int}
        """
        notices = ProcurementNoticeDao.instance().fetch_by_status(status=20, platform=self.PLATFORM, limit=limit)
        if not notices:
            logger.info("[parse_detail] 没有待解析的记录")
            return {"total": 0, "success": 0, "failed": 0}

        logger.info(f"[parse_detail] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, notice in enumerate(notices, 1):
            html = notice.html
            if not html:
                logger.warning(f"[parse_detail] {idx}/{len(notices)} 跳过: 无HTML内容")
                failed += 1
                continue

            try:
                # 先按本平台 HTML 结构过滤无用内容，再传给 LLM
                cleaned_text = self._clean_html_for_llm(html)
                llm_result = LLMParser.parse(CCGPCrawler.PROMPT + cleaned_text)

                # 提取子表列表数据（这些字段不在 ProcurementNotice 模型中）
                sub_attachments = llm_result.pop("notice_attachments", None) or []
                sub_packages = llm_result.pop("notice_packages", None) or []
                sub_qualifications = llm_result.pop("notice_qualifications", None) or []

                # LLM 返回的字段名已与 ProcurementNotice 对齐，直接遍历填充主表
                for key, value in llm_result.items():
                    if value is not None and value != "" and hasattr(notice, key):
                        setattr(notice, key, value)

                # LLM 解析后补充标准化字段
                self._enrich_notice(notice)

                notice.status = 30
                ok = ProcurementNoticeDao.instance().update_parsed(notice)
                if ok:
                    # 主表更新成功后再插入子表数据
                    NoticeAttachmentDao.instance().insert(notice.id, sub_attachments)
                    NoticePackageDao.instance().insert(notice.id, sub_packages)
                    NoticeQualificationDao.instance().insert(notice.id, sub_qualifications)
                    success += 1
                    logger.info(f"[parse_detail-llm] {idx}/{len(notices)} 成功: {notice.project_name[:40]}...")
                else:
                    failed += 1
                    logger.error(f"[parse_detail] {idx}/{len(notices)} 更新DB失败: id={notice.id}")
            except Exception as e:
                failed += 1
                logger.error(f"[parse_detail] {idx}/{len(notices)} 解析失败: {e}")

        logger.info(f"[parse_detail] 完成: 成功 {success} 条, 失败 {failed} 条")
        return {"total": len(notices), "success": success, "failed": failed}

    # ========================================================================
    # 兼容方法：一键运行（保留用于快速测试或全量跑通）
    # ========================================================================

    def run(
            self,
            pages: Optional[int] = 1,
    ) -> dict:
        """一键运行三步流程（fetch_list → fetch_html → parse_detail）.

        主要用于快速测试或一次性全量跑通，生产环境建议分进程执行。
        """
        logger.info("=" * 60)
        logger.info(f"[run] 开始三步流程 - 栏目: {self.part}")
        logger.info("=" * 60)

        # 1. fetch_list
        list_stats = self.fetch_list(pages=pages)

        # 2. fetch_html
        html_stats = self.fetch_html(limit=9999)

        # 3. parse_detail
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
