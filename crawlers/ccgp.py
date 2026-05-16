"""中国政府采购网爬虫实现."""
import re
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .db_storage import MySQLStorage
from .llm_parser import LLMParser
from .models import BidNotice
from .storage import Storage


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
    - 地方公告 (dfgg): http://www.ccgp.gov.cn/cggg/dfgg/
    - 中央公告 (zygg): http://www.ccgp.gov.cn/cggg/zygg/
    """

    BASE_URL = "http://www.ccgp.gov.cn"

    # 栏目映射
    COLUMNS = {
        "dfgg": "/cggg/dfgg/",   # 地方公告
        "zygg": "/cggg/zygg/",   # 中央公告
    }

    def __init__(
        self,
        column: str = "dfgg",
        delay: float = 1.0,
        max_retries: int = 3,
        timeout: int = 30,
        storage: Optional[Storage] = None,
        llm_parser: Optional[LLMParser] = None,
        db_storage: Optional[MySQLStorage] = None,
    ):
        """初始化爬虫.

        Args:
            column: 栏目代码，'dfgg'(地方公告) 或 'zygg'(中央公告)
            delay: 请求间隔（秒）
            max_retries: 最大重试次数
            timeout: 请求超时时间
            storage: 存储器实例（用于内存/文件去重，可选）
            llm_parser: LLM 解析器实例（可选）
            db_storage: MySQL 存储器实例（直接写入 procurement_notices 表）
        """
        if column not in self.COLUMNS:
            raise ValueError(f"不支持的栏目: {column}，可选: {list(self.COLUMNS.keys())}")

        self.column = column
        self.column_path = self.COLUMNS[column]
        self.list_base_url = urljoin(self.BASE_URL, self.column_path)
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.storage = storage or Storage()
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

    def _extract_total_pages(self, html: str) -> int:
        """从列表页HTML中提取总页数."""
        # 匹配 Pager({size:25, current:1, ...})
        match = re.search(r"Pager\(\{size:(\d+)", html)
        if match:
            return int(match.group(1))
        # 兜底：如果没有分页脚本，默认1页
        return 1

    def _build_list_url(self, page: int) -> str:
        """构建列表页URL.

        第1页: index.htm
        第2页+: index_2.htm, index_3.htm ...
        """
        if page <= 1:
            return urljoin(self.list_base_url, "index.htm")
        return urljoin(self.list_base_url, f"index_{page}.htm")

    def _parse_list_page(self, html: str, list_url: str) -> List[BidNotice]:
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

            notice = BidNotice()
            notice.title = a.get_text(strip=True)
            href = a["href"]
            # 拼接绝对URL
            notice.url = urljoin(list_url, href)
            notice.list_page = list_url

            # 提取 <em rel="bxlx"> 公告类型
            em_type = li.find("em", attrs={"rel": "bxlx"})
            if em_type:
                notice.notice_type = em_type.get_text(strip=True)

            # 使用正则从整个 li 文本中提取字段（更可靠）
            li_text = li.get_text(separator=" ", strip=True)

            # 发布时间：2026-05-14 15:30
            m = re.search(r"发布时间[：:]\s*([\d\-]{10}\s+\d{2}:\d{2})", li_text)
            if m:
                notice.publish_time = m.group(1).strip()

            # 地域：xxx（注意地域可能为空）
            m = re.search(r"地域[：:]\s*([^\s]+?)(?:\s+采购人|$)", li_text)
            if m:
                notice.region = m.group(1).strip()

            # 采购人：xxx（通常是最后一部分）
            m = re.search(r"采购人[：:]\s*(.+)$", li_text)
            if m:
                notice.purchaser = m.group(1).strip()

            notices.append(notice)

        return notices

    def _parse_detail_page(self, html: str, notice: BidNotice, use_llm: bool = False) -> BidNotice:
        """解析详情页，填充详细信息.

        Args:
            html: 详情页 HTML
            notice: 待填充的公告对象
            use_llm: 是否使用 LLM 解析（需要初始化时传入 llm_parser）
        """
        if use_llm and self.llm_parser is not None:
            notice = self.llm_parser.parse(html, notice)
            # LLM 解析后，仍保留原始 HTML 正文（如果 content_text 仍为空）
            soup = BeautifulSoup(html, "lxml")
            content_div = soup.find("div", class_="vF_detail_content")
            if content_div:
                notice.content_html = str(content_div)
                if not notice.content_text:
                    text = content_div.get_text(separator="\n", strip=True)
                    notice.content_text = text
        else:
            soup = BeautifulSoup(html, "lxml")

            # 1. 标题（如果列表页标题被截断，用详情页的完整标题覆盖）
            header = soup.find("div", class_="vF_detail_header")
            if header:
                h2 = header.find("h2", class_="tc")
                if h2:
                    notice.title = h2.get_text(strip=True)

            # 2. 概要表格
            table_div = soup.find("div", class_="table")
            if table_div:
                table = table_div.find("table")
                if table:
                    self._parse_summary_table(table, notice)

            # 3. 正文内容
            content_div = soup.find("div", class_="vF_detail_content")
            if content_div:
                notice.content_html = str(content_div)
                # 提取纯文本，去掉多余空白
                text = content_div.get_text(separator="\n", strip=True)
                notice.content_text = text

        # 4. 解析/标准化额外字段（省市区、时间、项目编号）
        self._enrich_notice(notice)

        return notice

    def _enrich_notice(self, notice: BidNotice) -> None:
        """从已有字段中提取并标准化各类信息."""
        from .parser_utils import (
            extract_region,
            standardize_publish_time,
            extract_project_code,
            parse_time_range,
            parse_amount,
            amount_to_fen,
            parse_purchaser_contact_person,
        )

        # 省市区、时间、项目编号
        notice.province, notice.city, notice.district = extract_region(
            address=notice.purchaser_address,
            region=notice.region,
            administrative_region=notice.administrative_region,
        )
        notice.publish_time_std = standardize_publish_time(notice.publish_time)
        notice.project_code = extract_project_code(notice.content_text, notice.title)

        # 采购方信息
        notice.purchaser_name = notice.purchaser_unit or notice.purchaser or None
        notice.purchaser_address_std = notice.purchaser_address
        notice.purchaser_contact_person = (
            parse_purchaser_contact_person(notice.content_text)
            or notice.contact_person
        )
        notice.purchaser_contact_phone = notice.purchaser_contact

        # 代理机构信息
        notice.agency_name_std = notice.agency_name
        notice.agency_address_std = notice.agency_address
        notice.agency_contact_phone = notice.agency_contact

        # 项目联系信息
        notice.project_contact_person = notice.contact_person
        notice.project_contact_phone = notice.contact_phone

        # 金额（整数分）
        notice.budget_amount_fen = amount_to_fen(parse_amount(notice.budget_amount))

        # 采购文件获取时间拆分
        notice.bid_doc_start_time, notice.bid_doc_end_time = parse_time_range(
            notice.bid_document_time
        )

        # 投标相关
        notice.response_deadline = standardize_publish_time(notice.bid_open_time)
        notice.bid_start_time = standardize_publish_time(notice.bid_open_time)
        notice.bid_location_std = notice.bid_open_location

    def _parse_summary_table(self, table, notice: BidNotice) -> None:
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

    def _map_field(self, label: str, value: str, notice: BidNotice) -> None:
        """将表格标签映射到模型字段.

        支持同义词映射，以兼容不同公告类型（公开招标、竞争性磋商、中标公告等）。
        """
        mapping = {
            # 项目名称
            "采购项目名称": "project_name",
            "项目名称": "project_name",
            # 品目
            "品目": "category",
            # 采购单位
            "采购单位": "purchaser_unit",
            # 行政区域
            "行政区域": "administrative_region",
            # 获取文件时间（招标/采购/磋商 等）
            "获取招标文件时间": "bid_document_time",
            "获取采购文件时间": "bid_document_time",
            "招标文件获取时间": "bid_document_time",
            "采购文件获取时间": "bid_document_time",
            # 文件售价
            "招标文件售价": "bid_document_price",
            "采购文件售价": "bid_document_price",
            "文件售价": "bid_document_price",
            # 获取文件地点
            "获取招标文件的地点": "bid_document_location",
            "获取采购文件的地点": "bid_document_location",
            "获取文件的地点": "bid_document_location",
            "招标文件获取地点": "bid_document_location",
            # 开标/开启时间
            "开标时间": "bid_open_time",
            "响应文件开启时间": "bid_open_time",
            "开标日期": "bid_open_time",
            "投标截止时间": "bid_open_time",
            "提交投标文件截止时间": "bid_open_time",
            # 开标/开启地点
            "开标地点": "bid_open_location",
            "响应文件开启地点": "bid_open_location",
            "投标地点": "bid_open_location",
            # 预算金额
            "预算金额": "budget_amount",
            "总预算金额": "budget_amount",
            "采购预算": "budget_amount",
            # 中标金额
            "总中标金额": "total_bid_amount",
            "中标金额": "total_bid_amount",
            "成交金额": "total_bid_amount",
            # 评审专家
            "评审专家名单": "review_experts",
            "评审专家": "review_experts",
            # 联系人
            "项目联系人": "contact_person",
            "联系人": "contact_person",
            # 联系电话
            "项目联系电话": "contact_phone",
            "联系电话": "contact_phone",
            # 采购单位地址
            "采购单位地址": "purchaser_address",
            "单位地址": "purchaser_address",
            # 采购单位联系方式
            "采购单位联系方式": "purchaser_contact",
            "单位联系方式": "purchaser_contact",
            # 代理机构
            "代理机构名称": "agency_name",
            "代理机构": "agency_name",
            # 代理机构地址
            "代理机构地址": "agency_address",
            # 代理机构联系方式
            "代理机构联系方式": "agency_contact",
            # 公告时间（可覆盖列表页的 publish_time）
            "公告时间": "publish_time",
        }

        field_name = mapping.get(label)
        if field_name:
            setattr(notice, field_name, value or None)

        # 附件
        if label.startswith("附件") and value:
            notice.attachments.append(value)

    def fetch_list(
        self,
        pages: Optional[int] = None,
        region_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        keyword_filter: Optional[str] = None,
    ) -> List[BidNotice]:
        """爬取列表页.

        Args:
            pages: 指定爬取页数，None则爬取全部
            region_filter: 按地域过滤（如"北京"、"辽宁"）
            type_filter: 按公告类型过滤（如"公开招标"、"中标公告"）
            keyword_filter: 按标题关键词过滤

        Returns:
            招标公告列表
        """
        # 先获取第1页，提取总页数
        first_page_html = self._get(self._build_list_url(1))
        if not first_page_html:
            print("[错误] 无法获取第1页列表")
            return []

        total_pages = self._extract_total_pages(first_page_html)
        print(f"[信息] 检测到总页数: {total_pages}")

        if pages is not None:
            total_pages = min(pages, total_pages)
            print(f"[信息] 本次计划爬取: {total_pages} 页")

        all_notices = []

        # 解析第1页
        notices = self._parse_list_page(first_page_html, self._build_list_url(1))
        all_notices.extend(self._filter(notices, region_filter, type_filter, keyword_filter))
        print(f"[进度] 第1页/{total_pages} 获取 {len(notices)} 条，累计 {len(all_notices)} 条")

        # 解析后续页
        for page in range(2, total_pages + 1):
            time.sleep(self.delay)
            url = self._build_list_url(page)
            html = self._get(url)
            if not html:
                continue

            notices = self._parse_list_page(html, url)
            filtered = self._filter(notices, region_filter, type_filter, keyword_filter)
            all_notices.extend(filtered)
            print(f"[进度] 第{page}页/{total_pages} 获取 {len(notices)} 条，匹配 {len(filtered)} 条，累计 {len(all_notices)} 条")

        # 去重
        all_notices = self.storage.dedup(all_notices)
        print(f"[完成] 列表页爬取结束，共 {len(all_notices)} 条（去重后）")
        return all_notices

    def fetch_details(self, notices: List[BidNotice], use_llm: bool = False) -> List[BidNotice]:
        """爬取详情页，补充详细信息.

        Args:
            notices: 招标公告列表
            use_llm: 是否使用 LLM 解析详情页

        Returns:
            补充详情后的列表
        """
        results = []
        total = len(notices)
        parser_type = "LLM" if (use_llm and self.llm_parser) else "HTML"
        for idx, notice in enumerate(notices, 1):
            time.sleep(self.delay)
            html = self._get(notice.url)
            if html:
                self._parse_detail_page(html, notice, use_llm=use_llm)
                results.append(notice)
                print(f"[详情-{parser_type}] {idx}/{total} {notice.title[:40]}...")
            else:
                print(f"[详情] {idx}/{total} 失败: {notice.url}")

        print(f"[完成] 详情页爬取结束（{parser_type}解析），成功 {len(results)}/{total}")
        return results

    def _filter(
        self,
        notices: List[BidNotice],
        region: Optional[str],
        notice_type: Optional[str],
        keyword: Optional[str],
    ) -> List[BidNotice]:
        """过滤公告列表."""
        result = notices
        if region:
            result = [n for n in result if region in (n.region or "")]
        if notice_type:
            result = [n for n in result if notice_type in (n.notice_type or "")]
        if keyword:
            result = [n for n in result if keyword in (n.title or "")]
        return result

    def run(
        self,
        pages: Optional[int] = 1,
        fetch_detail: bool = False,
        use_llm: bool = False,
        region: Optional[str] = None,
        notice_type: Optional[str] = "招标公告",
        keyword: Optional[str] = None,
    ) -> List[BidNotice]:
        """一键运行爬虫.

        Args:
            pages: 爬取页数
            fetch_detail: 是否爬取详情页
            use_llm: 是否使用 LLM 解析详情页
            region: 地域过滤
            notice_type: 类型过滤，默认只保留"招标公告"
            keyword: 关键词过滤

        Returns:
            爬取结果列表
        """
        print("=" * 60)
        print(f"开始爬取中国政府采购网 - 栏目: {self.column}")
        print(f"参数: pages={pages}, detail={fetch_detail}, use_llm={use_llm}, region={region}, type={notice_type}, keyword={keyword}")
        print("=" * 60)

        # 1. 爬取列表
        notices = self.fetch_list(
            pages=pages,
            region_filter=region,
            type_filter=notice_type,
            keyword_filter=keyword,
        )

        if not notices:
            print("[警告] 没有获取到任何数据")
            return []

        print(f"[过滤] 公告类型过滤后共 {len(notices)} 条")

        # 2. 爬取详情（可选）
        if fetch_detail:
            notices = self.fetch_details(notices, use_llm=use_llm)

        # 3. 存入数据库（如果配置了 db_storage）
        if self.db_storage:
            # 3.1 先基于数据库 URL 去重
            notices = self.db_storage.dedup_by_url(notices)
            print(f"[去重] 数据库去重后剩 {len(notices)} 条")

            if notices:
                stats = self.db_storage.save_notices(notices)
                print(
                    f"[数据库] 保存完成: 新增 {stats['inserted']} 条, "
                    f"更新 {stats['updated']} 条, 失败 {stats['failed']} 条"
                )
        else:
            print("[提示] 未配置 db_storage，结果不写入数据库")

        print("=" * 60)
        print(f"爬虫运行完成，共处理 {len(notices)} 条记录")
        print("=" * 60)
        return notices
