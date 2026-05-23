"""公告信息解析工具.

提供从招标公告文本和元数据中提取标准化字段的辅助函数.

注意：
- 本模块只包含【通用】文本/时间/金额解析逻辑，不依赖任何平台的 HTML 结构。
- 平台相关的 HTML 提取/清理逻辑（如针对特定 DOM 选择器）应放在各平台爬虫类中。
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# 省市区解析
# ---------------------------------------------------------------------------

_PROVINCE_MAP = {
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
}


def extract_region(
    address: Optional[str] = None,
    region: Optional[str] = None,
    administrative_region: Optional[str] = None,
) -> Tuple[str, str, str]:
    """从地址信息中解析省、市、区/县.

    返回: (province, city, district)，解析失败时返回空字符串
    """
    province = city = district = ""

    # --- 省份 ---
    if region:
        province = _normalize_province(region)
    elif administrative_region:
        m = re.match(r"(.+?省|.+?自治区|北京市|上海市|天津市|重庆市)", administrative_region)
        if m:
            province = m.group(1)
        else:
            province = _normalize_province(administrative_region)

    # --- 市 ---
    if address:
        m = re.search(r"([^\s省市县区]{2,8}?)市", address)
        if m:
            prefix = m.group(1)
            if prefix not in ("省", "自治", "直辖", "县", "州"):
                city = prefix + "市"

    # --- 区/县 ---
    if address:
        candidates = re.findall(r"([^\s省市县区]{2,8}?)区", address)
        for prefix in candidates:
            if prefix not in ("市辖", "直辖") and not prefix.endswith("自治"):
                district = prefix + "区"
                break
        if not district:
            candidates = re.findall(r"([^\s省市县区]{2,8}?)县", address)
            for prefix in candidates:
                if prefix not in ("直辖",) and not prefix.endswith("自治"):
                    district = prefix + "县"
                    break

    # fallback: administrative_region 本身可能是县级市
    if not city and administrative_region:
        if (
            administrative_region.endswith("市")
            and administrative_region not in ("北京市", "上海市", "天津市", "重庆市")
        ):
            city = administrative_region

    return province or "", city or "", district or ""


def _normalize_province(name: str) -> str:
    """将省份简称或名称标准化为全称."""
    name = name.strip()
    if name in _PROVINCE_MAP:
        return _PROVINCE_MAP[name]
    if name in ("北京", "上海", "天津", "重庆"):
        return name + "市"
    if name in ("香港", "澳门"):
        return name + "特别行政区"
    if not name.endswith(("省", "市", "区", "自治区", "特别行政区")):
        return name + "省"
    return name


# ---------------------------------------------------------------------------
# 发布时间标准化
# ---------------------------------------------------------------------------

_DT_PATTERNS = [
    # 2026年05月15日  16:55
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})", "%Y-%m-%d %H:%M"),
    # 2026年05月15日  16点55分
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2})点(\d{2})分", "%Y-%m-%d %H:%M"),
    # 2026-05-15 16:55
    (r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", "%Y-%m-%d %H:%M"),
    # 2026/05/15 16:55
    (r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})", "%Y-%m-%d %H:%M"),
    # 2026年05月15日（无时间）
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "%Y-%m-%d"),
    # 2026-05-15
    (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
    # 2026/05/15
    (r"(\d{4})/(\d{2})/(\d{2})", "%Y-%m-%d"),
]


def standardize_publish_time(publish_time: Optional[str]) -> str:
    """将发布时间统一为标准格式: YYYY-MM-DD HH:MM.

    示例:
        >>> standardize_publish_time("2026年05月15日  16:55")
        '2026-05-15 16:55'
        >>> standardize_publish_time("2026-05-14 15:30")
        '2026-05-14 15:30'
        >>> standardize_publish_time("2026年06月01日  09点30分")
        '2026-06-01 09:30'
    """
    if not publish_time:
        return ""

    text = publish_time.strip()
    for pattern, fmt in _DT_PATTERNS:
        m = re.match(pattern, text)
        if m:
            try:
                normalized = (
                    m.group(0)
                    .replace("年", "-")
                    .replace("月", "-")
                    .replace("日", "")
                    .replace("/", "-")
                    .replace("点", ":")
                    .replace("分", "")
                )
                dt = datetime.strptime(normalized, fmt)
                if "%H" in fmt:
                    return dt.strftime("%Y-%m-%d %H:%M")
                else:
                    return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return ""


# ---------------------------------------------------------------------------
# 时间范围解析（采购文件获取时间拆分）
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?")
_TIME_RE = re.compile(r"(\d{1,2})[：:](\d{2})")


def parse_time_range(text: Optional[str]) -> Tuple[str, str]:
    """从时间范围文本解析开始和结束时间.

    支持格式:
        - "2026年05月17日至2026年05月24日每日上午:00:00 至 12:00"
        - "2026-05-15 09:00 至 2026-05-24 17:00"
        - "2026年05月15日至2026年05月24日，每天上午9：00至12：00，下午14：00至17：00"

    返回: (start_time, end_time)，格式均为 YYYY-MM-DD HH:MM，解析失败返回 ("", "")

    示例:
        >>> parse_time_range("2026年05月17日至2026年05月24日每日上午:00:00 至 12:00 下午:12:00 至 23:59")
        ('2026-05-17 00:00', '2026-05-24 23:59')
    """
    if not text:
        return "", ""

    # 提取所有日期
    dates = []
    for m in _DATE_RE.finditer(text):
        dates.append(f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}")

    start_date = dates[0] if len(dates) >= 1 else None
    end_date = dates[1] if len(dates) >= 2 else start_date

    # 提取所有时间
    times = []
    for m in _TIME_RE.finditer(text):
        times.append(f"{m.group(1).zfill(2)}:{m.group(2)}")

    start_time = times[0] if len(times) >= 1 else "00:00"
    end_time = times[-1] if len(times) >= 1 else "23:59"

    start = f"{start_date} {start_time}" if start_date else ""
    end = f"{end_date} {end_time}" if end_date else ""
    return start, end


# ---------------------------------------------------------------------------
# 金额解析
# ---------------------------------------------------------------------------

_AMOUNT_PATTERNS = [
    re.compile(r"[￥¥]?\s*([\d,.]+)\s*万\s*元"),
    re.compile(r"[￥¥]?\s*([\d,.]+)\s*元"),
    re.compile(r"^\s*([\d,.]+)\s*$"),
]


def parse_amount(text: Optional[str]) -> Optional[Decimal]:
    """将中文金额字符串解析为以【元】为单位的 Decimal.

    示例:
        >>> parse_amount("￥145.000000万元（人民币）")
        Decimal('1450000.0000')
        >>> parse_amount("797217.00 元")
        Decimal('797217.0000')
    """
    if not text:
        return ""

    text = text.strip()
    if not text or text in ("-", "—", "无", "null", "NULL"):
        return ""

    m = _AMOUNT_PATTERNS[0].search(text)
    if m:
        try:
            num = Decimal(m.group(1).replace(",", ""))
            return (num * 10000).quantize(Decimal("0.0001"))
        except Exception:
            pass

    m = _AMOUNT_PATTERNS[1].search(text)
    if m:
        try:
            return Decimal(m.group(1).replace(",", "")).quantize(Decimal("0.0001"))
        except Exception:
            pass

    m = _AMOUNT_PATTERNS[2].match(text)
    if m:
        try:
            return Decimal(m.group(1).replace(",", "")).quantize(Decimal("0.0001"))
        except Exception:
            pass

    return None


def amount_to_fen(amount: Optional[Decimal]) -> Optional[int]:
    """将元为单位的 Decimal 金额转为整数【分】.

    示例:
        >>> amount_to_fen(Decimal('1450000.0000'))
        145000000
        >>> amount_to_fen(Decimal('797217.50'))
        79721750
    """
    if amount is None:
        return None
    try:
        # 先转成分，四舍五入到整数
        fen = int((amount * 100).quantize(Decimal("1")))
        return fen
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 项目编号解析
# ---------------------------------------------------------------------------

_PROJECT_CODE_PATTERNS = [
    re.compile(
        r"(?:项目编号|采购项目编号|招标编号|招标项目编号)[：:\s]+"
        r"([A-Za-z0-9\-–—_/【】\[\]（）()]+?)"
        r"(?=\n|\s|$|）|\)|，|,|；|;|。)",
        re.IGNORECASE,
    ),
    re.compile(r"（项目编号[：:\s]*([A-Za-z0-9\-–—_/【】\[\]（）()]+?)）"),
    re.compile(r"\(项目编号[：:\s]*([A-Za-z0-9\-–—_/【】\[\]（）()]+?)\)"),
    re.compile(
        r"原公告的(?:采购项目编号|项目编号)[：:\s]+"
        r"([A-Za-z0-9\-–—_/【】\[\]（）()]+?)"
        r"(?=\n|\s|$|）|\)|，|,|；|;|。)"
    ),
]


def extract_project_code(
    content_text: Optional[str], title: Optional[str] = None
) -> str:
    """从正文或标题中提取项目编号，未找到返回空字符串."""
    if not content_text and not title:
        return ""

    texts = []
    if content_text:
        texts.append(content_text)
    if title:
        texts.append(title)

    for text in texts:
        for pattern in _PROJECT_CODE_PATTERNS:
            m = pattern.search(text)
            if m:
                code = m.group(1).strip()
                code = re.sub(r"[，,；;.\s]+$", "", code)
                if code and len(code) >= 3:
                    return code

    return None


# ---------------------------------------------------------------------------
# 采购方联系人解析
# ---------------------------------------------------------------------------

def parse_purchaser_contact_person(content_text: Optional[str]) -> str:
    """从正文'采购人信息'区块中尝试提取联系人姓名，未找到返回空字符串.

    大部分政府采购公告的采购人信息只有名称、地址、联系方式，
    没有单独列联系人。本函数做尽力而为的提取。
    """
    if not content_text:
        return ""

    # 匹配 "采购人信息" 区块后 500 字符内的 "联系人"
    m = re.search(
        r"(?:采购人信息|1\.\s*采购人信息)[\s\S]{0,800}?"
        r"联系人[：:\s]+([^\n，,；;。]{2,20})",
        content_text,
    )
    if m:
        name = m.group(1).strip()
        # 过滤掉纯电话号码
        if re.search(r"[\u4e00-\u9fa5]", name):
            return name
    return None


# ---------------------------------------------------------------------------
# HTML 噪声过滤（保留 HTML 结构，去掉 head/foot/css/js）
# ---------------------------------------------------------------------------
# 说明：此函数较为通用，仅移除标准噪声标签（script/style/nav 等），
# 不依赖特定平台的 DOM 结构。如需平台定制，请在平台爬虫类中重写。

_NOISE_HTML_TAGS = {"head", "script", "style", "nav", "footer", "header", "iframe", "noscript", "aside", "svg", "canvas", "link", "meta"}


def parse_chinese_datetime(text: Optional[str]) -> Optional[datetime]:
    """解析中文日期时间字符串为 datetime 对象.

    示例:
        >>> parse_chinese_datetime("2026年05月15日  16:55")
        datetime(2026, 5, 15, 16, 55)
        >>> parse_chinese_datetime("2026-05-14 15:30")
        datetime(2026, 5, 14, 15, 30)
    """
    if not text:
        return None
    text = str(text).strip()
    for pattern, fmt in _DT_PATTERNS:
        m = re.match(pattern, text)
        if m:
            try:
                normalized = (
                    m.group(0)
                    .replace("年", "-")
                    .replace("月", "-")
                    .replace("日", "")
                    .replace("/", "-")
                    .replace("点", ":")
                    .replace("分", "")
                )
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
    return None


def to_decimal(value) -> Optional[Decimal]:
    """将任意值转为 Decimal，失败返回 None."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return None


def to_tinyint(value) -> int:
    """将任意值转为 tinyint (0/1)."""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "是", "有", "需要", "要求"):
        return 1
    return 0


def parse_crawled_at(value) -> datetime:
    """解析爬取时间，失败返回当前时间."""
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now()


def strip_html_noise(html: str) -> str:
    """去掉 HTML 中的 head/foot/css/js 等噪声标签，保留正文 HTML 结构.

    适用于 fetch_html 阶段存储过滤后的详情页 HTML。

    Args:
        html: 原始 HTML 字符串

    Returns:
        过滤后的 HTML 字符串
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # 去掉已知噪声标签及其内容
    for tag in soup.find_all(_NOISE_HTML_TAGS):
        tag.decompose()

    # 返回过滤后的 HTML（优先 body，否则整个文档）
    body = soup.find("body")
    if body:
        return str(body)
    return str(soup)
