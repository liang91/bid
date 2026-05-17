"""中国政府采购网爬虫实现."""
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .db_storage import MySQLStorage
from .llm_parser import LLMParser
from .models import ProcurementNotice
from .parser_utils import clean_html_for_llm, strip_html_noise

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

    def __init__(
            self,
            part: str = "dfgg",
            delay: float = 1.0,
            max_retries: int = 3,
            timeout: int = 30,
            llm_parser: Optional[LLMParser] = None,
            db_storage: Optional[MySQLStorage] = None,
    ):
        """初始化爬虫.

        Args:
            part: 栏目代码，'dfgg'(地方公告) 或 'zygg'(中央公告)
            delay: 请求间隔（秒）
            max_retries: 最大重试次数
            timeout: 请求超时时间
            llm_parser: LLM 解析器实例（可选）
            db_storage: MySQL 存储器实例（直接写入 procurement_notices 表）
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
        self.llm_parser = llm_parser
        self.db_storage = db_storage
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
                print(f"[HTTP {resp.status_code}] {url}")
            except requests.RequestException as e:
                print(f"[请求失败] 第{attempt}次尝试: {url} - {e}")
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
            print(f"[解析] 未找到列表容器: {list_url}")
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

    def _parse_detail_page(self, html: str, notice: ProcurementNotice, use_llm: bool = False) -> ProcurementNotice:
        """解析详情页，填充详细信息.

        Args:
            html: 详情页 HTML
            notice: 待填充的公告对象
            use_llm: 是否使用 LLM 解析（需要初始化时传入 llm_parser）
        """
        if use_llm and self.llm_parser is not None:
            notice = self.llm_parser.parse(html, notice)
            # LLM 解析后，仍保留原始 HTML 正文（如果 raw_abstract 仍为空）
            soup = BeautifulSoup(html, "lxml")
            content_div = soup.find("div", class_="vF_detail_content")
            if content_div:
                notice.html = str(content_div)
                if not notice.raw_abstract:
                    text = content_div.get_text(separator="\n", strip=True)
                    notice.raw_abstract = text
        else:
            soup = BeautifulSoup(html, "lxml")

            # 1. 标题（如果列表页标题被截断，用详情页的完整标题覆盖）
            header = soup.find("div", class_="vF_detail_header")
            if header:
                h2 = header.find("h2", class_="tc")
                if h2:
                    notice.project_name = h2.get_text(strip=True)

            # 2. 概要表格
            table_div = soup.find("div", class_="table")
            if table_div:
                table = table_div.find("table")
                if table:
                    self._parse_summary_table(table, notice)

            # 3. 正文内容
            content_div = soup.find("div", class_="vF_detail_content")
            if content_div:
                notice.html = str(content_div)
                # 提取纯文本，去掉多余空白
                text = content_div.get_text(separator="\n", strip=True)
                notice.raw_abstract = text

        # 4. 解析/标准化额外字段（省市区、时间、项目编号）
        self._enrich_notice(notice)

        return notice

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
            region=notice.region,
            administrative_region=notice.purchaser_region,
        )

        # 公告发布时间标准化
        if notice.notice_date:
            notice.notice_date = standardize_publish_time(notice.notice_date)

        # 项目编号
        notice.project_no = extract_project_code(notice.raw_abstract, notice.project_name)

        # 采购方联系人（从正文尽力提取，如果表格中未提供）
        if not notice.purchaser_contact_person:
            notice.purchaser_contact_person = parse_purchaser_contact_person(notice.raw_abstract)

        # 采购文件获取时间拆分（doc_obtain_start 先存了原始范围文本）
        if notice.doc_obtain_start:
            notice.doc_obtain_start, notice.doc_obtain_end = parse_time_range(notice.doc_obtain_start)

        # 投标截止时间 / 开标时间标准化
        if notice.bid_open_time:
            _std = standardize_publish_time(notice.bid_open_time)
            notice.bid_deadline = _std
            notice.bid_open_time = _std

    def _parse_summary_table(self, table, notice: ProcurementNotice) -> None:
        """解析详情页概要表格.

        表格特征：
        - label 单元格通常有 class='title'
        - 一行可能是 2 列（label + value）或 4 列（label+value label+value）
        - 也存在 label 和 value 连续出现但没有 class 的情况
        """
        rows = table.find_all("tr")
        for row in rows:
            tds = row.find_all(["td", "th"])
            if not tds:
                continue

            i = 0
            while i < len(tds):
                td = tds[i]
                classes = td.get("class") or []
                text = td.get_text(strip=True)

                # 跳过纯空或纯分隔符单元格
                if not text or text == "公告信息：" or text == "联系人及联系方式：":
                    i += 1
                    continue

                # 如果当前 td 是 title 类，则它一定是 label
                if "title" in classes:
                    label = text
                    value = ""
                    # 找下一个非 title 的 td 作为值
                    if i + 1 < len(tds):
                        next_td = tds[i + 1]
                        next_classes = next_td.get("class") or []
                        if "title" not in next_classes:
                            value = next_td.get_text(strip=True)
                            i += 1  # 跳过值列
                    self._map_field(label, value, notice)
                else:
                    # 非 title 单元格，尝试把它当 label（兼容无 class 的表格）
                    # 但只做简单的关键词匹配，避免误解析
                    if i + 1 < len(tds):
                        next_td = tds[i + 1]
                        next_text = next_td.get_text(strip=True)
                        # 如果当前文本像 label（包含常见关键词且较短）
                        if self._looks_like_label(text) and len(text) < 20:
                            self._map_field(text, next_text, notice)
                            i += 1  # 跳过值列
                i += 1

    def _looks_like_label(self, text: str) -> bool:
        """判断文本是否像表格 label."""
        keywords = [
            "项目", "名称", "品目", "单位", "区域", "时间", "地点", "地址",
            "售价", "金额", "联系人", "电话", "方式", "代理", "评审", "专家",
            "公告", "预算", "开标", "中标", "招标", "采购", "响应", "文件",
        ]
        return any(kw in text for kw in keywords)

    def _map_field(self, label: str, value: str, notice: ProcurementNotice) -> None:
        """将表格标签映射到 ProcurementNotice 模型字段.

        字段名已与 procurement_notices SQL 表一一对应。
        支持同义词映射，以兼容不同公告类型。
        """
        mapping = {
            # 项目名称
            "采购项目名称": "project_name",
            "项目名称": "project_name",
            # 品目
            "品目": "category_name",
            # 采购单位
            "采购单位": "purchaser_name",
            # 行政区域
            "行政区域": "purchaser_region",
            # 获取文件时间（招标/采购/磋商 等）→ 暂存到 doc_obtain_start，后续 _enrich_notice 拆分
            "获取招标文件时间": "doc_obtain_start",
            "获取采购文件时间": "doc_obtain_start",
            "招标文件获取时间": "doc_obtain_start",
            "采购文件获取时间": "doc_obtain_start",
            # 文件售价
            "招标文件售价": "doc_price",
            "采购文件售价": "doc_price",
            "文件售价": "doc_price",
            # 获取文件地点
            "获取招标文件的地点": "bid_platform",
            "获取采购文件的地点": "bid_platform",
            "获取文件的地点": "bid_platform",
            "招标文件获取地点": "bid_platform",
            # 开标/开启时间
            "开标时间": "bid_open_time",
            "响应文件开启时间": "bid_open_time",
            "开标日期": "bid_open_time",
            "投标截止时间": "bid_open_time",
            "提交投标文件截止时间": "bid_open_time",
            # 开标/开启地点
            "开标地点": "bid_platform",
            "响应文件开启地点": "bid_platform",
            "投标地点": "bid_platform",
            # 预算金额
            "预算金额": "budget",
            "总预算金额": "budget",
            "采购预算": "budget",
            # 中标金额（结果公告用，公开招标通常无此字段）
            "总中标金额": "budget",
            "中标金额": "budget",
            "成交金额": "budget",
            # 联系人
            "项目联系人": "project_contact_person",
            "联系人": "project_contact_person",
            # 联系电话
            "项目联系电话": "project_contact_phone",
            "联系电话": "project_contact_phone",
            # 采购单位地址
            "采购单位地址": "purchaser_address",
            "单位地址": "purchaser_address",
            # 采购单位联系方式
            "采购单位联系方式": "purchaser_contact_phone",
            "单位联系方式": "purchaser_contact_phone",
            # 代理机构
            "代理机构名称": "agency_name",
            "代理机构": "agency_name",
            # 代理机构地址
            "代理机构地址": "agency_address",
            # 代理机构联系方式
            "代理机构联系方式": "agency_contact_phone",
            # 公告时间（可覆盖列表页的 notice_date）
            "公告时间": "notice_date",
        }

        field_name = mapping.get(label)
        if field_name:
            setattr(notice, field_name, value or "")

        # 附件
        if label.startswith("附件") and value:
            notice.attachments.append(value)

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
            print(f"[fetch_list] 第{page}页 获取 {len(notices)} 条，累计 {len(all_notices)} 条")

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
        print(f"[fetch_list] 去重后共 {len(all_notices)} 条")

        # 过滤：仅保留"招标公告"类型
        tender_notices = [n for n in all_notices if self._is_tender_notice(n)]
        excluded = len(all_notices) - len(tender_notices)
        if excluded > 0:
            print(f"[fetch_list] 排除非招标公告 {excluded} 条，保留 {len(tender_notices)} 条")

        # 存入数据库（INSERT IGNORE，跳过已存在的 URL）
        if tender_notices:
            stats = self.db_storage.insert_list_notices(tender_notices)
            print(
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
        notices = self.db_storage.fetch_by_status(status=1, platform=self.PLATFORM, limit=limit)
        if not notices:
            print("[fetch_html] 没有待获取 HTML 的记录")
            return {"total": 0, "success": 0, "failed": 0}

        print(f"[fetch_html] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, notice in enumerate(notices, 1):
            time.sleep(self.delay)
            html = self._get(notice.url)
            if html:
                # 去掉 head/foot/css/js 等噪声标签，保留正文 HTML 结构
                filtered_html = strip_html_noise(html)
                ok = self.db_storage.update_html_content(notice.id, filtered_html)
                if ok:
                    success += 1
                    print(f"[fetch_html] {idx}/{len(notices)} 成功: {notice.project_name[:40]}...")
                else:
                    failed += 1
                    print(f"[fetch_html] {idx}/{len(notices)} 更新DB失败: {notice.url}")
            else:
                failed += 1
                print(f"[fetch_html] {idx}/{len(notices)} 请求失败: {notice.url}")

        print(f"[fetch_html] 完成: 成功 {success} 条, 失败 {failed} 条")
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
        notices = self.db_storage.fetch_by_status(status=20, platform=self.PLATFORM, limit=limit)
        if not notices:
            print("[parse_detail] 没有待解析的记录")
            return {"total": 0, "success": 0, "failed": 0}

        print(f"[parse_detail] 共 {len(notices)} 条待处理")
        success = failed = 0

        for idx, notice in enumerate(notices, 1):
            html = notice.html
            if not html:
                print(f"[parse_detail] {idx}/{len(notices)} 跳过: 无HTML内容")
                failed += 1
                continue

            try:
                # 先过滤掉 header/foot/js/css，再传给 LLM
                cleaned_text = clean_html_for_llm(html)
                notice = self.llm_parser.parse(cleaned_text, notice)
                # LLM 解析后补充标准化字段
                self._enrich_notice(notice)

                notice.status = 30
                ok = self.db_storage.update_parsed_detail(notice)
                if ok:
                    success += 1
                    print(f"[parse_detail-llm] {idx}/{len(notices)} 成功: {notice.project_name[:40]}...")
                else:
                    failed += 1
                    print(f"[parse_detail] {idx}/{len(notices)} 更新DB失败: id={notice.id}")
            except Exception as e:
                failed += 1
                print(f"[parse_detail] {idx}/{len(notices)} 解析失败: {e}")

        print(f"[parse_detail] 完成: 成功 {success} 条, 失败 {failed} 条")
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
        print("=" * 60)
        print(f"[run] 开始三步流程 - 栏目: {self.part}")
        print("=" * 60)

        # 1. fetch_list
        list_stats = self.fetch_list(pages=pages)

        # 2. fetch_html
        html_stats = self.fetch_html(limit=9999)

        # 3. parse_detail
        parse_stats = self.parse_detail(limit=9999)

        print("=" * 60)
        print("[run] 三步流程全部完成")
        print(f"  fetch_list : 插入 {list_stats.get('inserted', 0)} 条")
        print(f"  fetch_html : 成功 {html_stats.get('success', 0)} 条")
        print(f"  parse_detail: 成功 {parse_stats.get('success', 0)} 条")
        print("=" * 60)
        return {
            "fetch_list": list_stats,
            "fetch_html": html_stats,
            "parse_detail": parse_stats,
        }
