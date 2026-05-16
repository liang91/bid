"""MySQL 数据库存储模块 — 写入 procurement_notices 表."""

import json
import re
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional

import pymysql
from pymysql.cursors import DictCursor

from .models import BidNotice


class MySQLStorage:
    """招标信息 MySQL 存储器，直接写入 procurement_notices 表.

    使用示例:
        storage = MySQLStorage(
            host="localhost",
            port=3306,
            user="root",
            password="your_password",
            database="bid"
        )
        storage.save_notices(notices)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "bid",
        charset: str = "utf8mb4",
    ):
        self.conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": charset,
            "cursorclass": DictCursor,
            "autocommit": False,
        }
        self._insert_sql = self._build_insert_sql()

    @contextmanager
    def _get_cursor(self):
        """获取数据库游标的上下文管理器."""
        conn = pymysql.connect(**self.conn_params)
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _build_insert_sql(self) -> str:
        """构建 INSERT ... ON DUPLICATE KEY UPDATE 语句."""
        fields = [
            "notice_type", "url", "platform",
            "region_province", "region_city", "region_district",
            "project_name", "project_no", "purchase_plan_no",
            "budget", "max_limit", "currency",
            "category_code", "category_name",
            "method", "joint_bid_allowed", "joint_bid_max_members", "sme_oriented",
            "notice_date", "doc_obtain_start", "doc_obtain_end",
            "bid_deadline", "bid_open_time",
            "bid_platform", "bid_platform_url", "ca_required", "doc_price",
            "purchaser_name", "purchaser_address", "purchaser_contact_person",
            "purchaser_contact_phone", "purchaser_region",
            "agency_name", "agency_address", "agency_contact_person",
            "agency_contact_phone", "agency_region",
            "project_contact_person", "project_contact_phone",
            "qualification_summary", "industry_tags", "keywords",
            "suggested_company_types", "geographic_advantage",
            "raw_abstract", "parse_time",
            "status", "created_at", "updated_at",
        ]
        columns = ", ".join(fields)
        placeholders = ", ".join([f"%({f})s" for f in fields])
        # ON DUPLICATE KEY UPDATE: 排除 auto_increment 和 created_at
        updates = ", ".join([f"{f}=VALUES({f})" for f in fields if f not in ("created_at",)])
        return (
            f"INSERT INTO procurement_notices ({columns}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )

    def save_notices(self, notices: List[BidNotice], batch_size: int = 100) -> dict:
        """批量保存公告到 MySQL procurement_notices 表，自动去重（基于 URL）并更新已存在记录.

        Args:
            notices: 招标公告列表
            batch_size: 每批插入数量

        Returns:
            {"inserted": int, "updated": int, "failed": int}
        """
        if not notices:
            return {"inserted": 0, "updated": 0, "failed": 0}

        inserted = updated = failed = 0
        batches = [
            notices[i : i + batch_size] for i in range(0, len(notices), batch_size)
        ]

        with self._get_cursor() as cursor:
            for batch in batches:
                params = [self._notice_to_dict(n) for n in batch]
                try:
                    cursor.executemany(self._insert_sql, params)
                    # ON DUPLICATE KEY: 1=insert, 2=update
                    # 精确统计：先查出已存在的
                    urls = [p["url"] for p in params]
                    existing_urls = self._find_existing(cursor, urls)
                    updated += len(existing_urls)
                    inserted += len(params) - len(existing_urls)
                except Exception as e:
                    print(f"[MySQLStorage] 批量写入失败: {e}")
                    failed += len(batch)

        return {"inserted": inserted, "updated": updated, "failed": failed}

    def _find_existing(self, cursor, urls: List[str]) -> set:
        """查询给定的 URL 中哪些已经存在."""
        if not urls:
            return set()
        existing = set()
        batch_size = 500
        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            placeholders = ", ".join(["%s"] * len(batch))
            cursor.execute(
                f"SELECT url FROM procurement_notices WHERE url IN ({placeholders})",
                tuple(batch),
            )
            for row in cursor.fetchall():
                existing.add(row["url"])
        return existing

    def notice_exists(self, url: str) -> bool:
        """公开方法：检查 URL 是否已存在."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM procurement_notices WHERE url = %s LIMIT 1", (url,))
            return cursor.fetchone() is not None

    def dedup_by_url(self, notices: List[BidNotice]) -> List[BidNotice]:
        """基于数据库已有 URL 去重，返回尚未入库的公告."""
        if not notices:
            return []

        urls = [n.url for n in notices if n.url]
        if not urls:
            return notices

        with self._get_cursor() as cursor:
            existing = self._find_existing(cursor, urls)

        return [n for n in notices if n.url not in existing]

    @staticmethod
    def _notice_to_dict(notice: BidNotice) -> dict:
        """将 BidNotice 转换为可插入 procurement_notices 的字典."""
        d = notice.to_dict()

        # ---------- 基础映射 ----------
        result = {
            "notice_type": d.get("notice_type") or "",
            "url": d.get("url") or "",
            "platform": d.get("source") or "中国政府采购网",

            "region_province": d.get("province") or "",
            "region_city": d.get("city") or "",
            "region_district": d.get("district") or "",

            "project_name": d.get("project_name") or d.get("title") or "",
            "project_no": d.get("project_code") or "",
            "purchase_plan_no": "",

            "budget": _to_decimal(parse_amount(d.get("budget_amount"))),
            "max_limit": _to_decimal(None),
            "currency": "CNY",

            "category_code": "",
            "category_name": d.get("category") or "",

            "method": d.get("notice_type") or "",
            "joint_bid_allowed": 0,
            "joint_bid_max_members": 1,
            "sme_oriented": 0,

            "notice_date": _to_datetime(parse_chinese_datetime(d.get("publish_time"))),
            "doc_obtain_start": _to_datetime(parse_chinese_datetime(d.get("bid_doc_start_time"))),
            "doc_obtain_end": _to_datetime(parse_chinese_datetime(d.get("bid_doc_end_time"))),
            "bid_deadline": _to_datetime(parse_chinese_datetime(d.get("response_deadline"))),
            "bid_open_time": _to_datetime(parse_chinese_datetime(d.get("bid_start_time"))),

            "bid_platform": "",
            "bid_platform_url": "",
            "ca_required": 0,
            "doc_price": _to_decimal(parse_amount(d.get("bid_document_price"))),

            "purchaser_name": d.get("purchaser_name") or d.get("purchaser") or "",
            "purchaser_address": d.get("purchaser_address_std") or d.get("purchaser_address") or "",
            "purchaser_contact_person": d.get("purchaser_contact_person") or d.get("contact_person") or "",
            "purchaser_contact_phone": d.get("purchaser_contact_phone") or d.get("purchaser_contact") or "",
            "purchaser_region": d.get("administrative_region") or d.get("region") or "",

            "agency_name": d.get("agency_name_std") or d.get("agency_name") or "",
            "agency_address": d.get("agency_address_std") or d.get("agency_address") or "",
            "agency_contact_person": d.get("contact_person") or "",
            "agency_contact_phone": d.get("agency_contact_phone") or d.get("agency_contact") or "",
            "agency_region": "",

            "project_contact_person": d.get("project_contact_person") or d.get("contact_person") or "",
            "project_contact_phone": d.get("project_contact_phone") or d.get("contact_phone") or "",

            "qualification_summary": None,
            "industry_tags": None,
            "keywords": None,
            "suggested_company_types": None,
            "geographic_advantage": "",

            "raw_abstract": d.get("content_text") or "",
            "parse_time": datetime.now(),

            "status": 1,
            "created_at": _parse_crawled_at(d.get("crawled_at")),
            "updated_at": datetime.now(),
        }

        # 清理空字符串为 None（除了 NOT NULL 且默认 '' 的字段已由上面处理）
        for key, val in result.items():
            if val == "":
                result[key] = None

        return result

    def execute(self, sql: str, params: Optional[tuple] = None):
        """执行原始 SQL（用于查询或维护）."""
        with self._get_cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()


# ---------------------------------------------------------------------------
# 辅助转换函数
# ---------------------------------------------------------------------------

def _to_decimal(val) -> Decimal:
    """将解析结果转为 Decimal，None 则返回 0.00."""
    if val is None:
        return Decimal("0.00")
    try:
        return Decimal(str(val)).quantize(Decimal("0.00"))
    except InvalidOperation:
        return Decimal("0.00")


def _to_datetime(val) -> Optional[datetime]:
    """将解析结果转为 datetime，None 则返回 None（让数据库用默认值）."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None) if val.tzinfo else val
    return None


def _parse_crawled_at(crawled) -> Optional[datetime]:
    """将 crawled_at 转为 datetime."""
    if isinstance(crawled, str):
        try:
            return datetime.fromisoformat(crawled.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    elif isinstance(crawled, datetime):
        return crawled.replace(tzinfo=None) if crawled.tzinfo else crawled
    return None


# ---------------------------------------------------------------------------
# 金额解析辅助函数
# ---------------------------------------------------------------------------

_AMOUNT_PATTERNS = [
    # 匹配 "￥145.000000万元（人民币）"
    re.compile(r"[￥¥]?\s*([\d,.]+)\s*万\s*元"),
    # 匹配 "797217.00 元" 或 "￥1,234.56元"
    re.compile(r"[￥¥]?\s*([\d,.]+)\s*元"),
    # 匹配纯数字（如果已经以元为单位）
    re.compile(r"^\s*([\d,.]+)\s*$"),
]


def parse_amount(text: Optional[str]) -> Optional[Decimal]:
    """将中文金额字符串解析为以【元】为单位的 Decimal."""
    """将中文金额字符串解析为以【元】为单位的 Decimal.

    支持的格式示例:
        - "￥145.000000万元（人民币）" -> 1450000.0
        - "797217.00 元"               -> 797217.00
        - "￥0.007972万元"             -> 79.72
        - "1,234.56元"                -> 1234.56
    """
    if not text:
        return None

    text = text.strip()
    if not text or text in ("-", "—", "无", "null", "NULL"):
        return None

    # 优先匹配 "万元"
    m = _AMOUNT_PATTERNS[0].search(text)
    if m:
        try:
            num = Decimal(m.group(1).replace(",", ""))
            return (num * 10000).quantize(Decimal("0.0001"))
        except InvalidOperation:
            pass

    # 再匹配 "元"
    m = _AMOUNT_PATTERNS[1].search(text)
    if m:
        try:
            return Decimal(m.group(1).replace(",", "")).quantize(Decimal("0.0001"))
        except InvalidOperation:
            pass

    # 兜底：纯数字
    m = _AMOUNT_PATTERNS[2].match(text)
    if m:
        try:
            return Decimal(m.group(1).replace(",", "")).quantize(Decimal("0.0001"))
        except InvalidOperation:
            pass

    return None


# ---------------------------------------------------------------------------
# 时间解析辅助函数
# ---------------------------------------------------------------------------

_DT_PATTERNS = [
    # "2026年05月15日  16:55"
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})"), "%Y-%m-%d %H:%M"),
    # "2026-05-15 16:55"
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})"), "%Y-%m-%d %H:%M"),
    # "2026/05/15 16:55"
    (re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})"), "%Y-%m-%d %H:%M"),
    # "2026年05月15日"（无时间）
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"), "%Y-%m-%d"),
    # "2026-05-15"
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "%Y-%m-%d"),
]


def parse_chinese_datetime(text: Optional[str]) -> Optional[datetime]:
    """解析常见中文/混合日期时间格式为 datetime 对象."""
    if not text:
        return None

    text = text.strip()
    for pattern, fmt in _DT_PATTERNS:
        m = pattern.match(text)
        if m:
            try:
                return datetime.strptime(m.group(0).replace("/", "-").replace("年", "-").replace("月", "-").replace("日", ""), fmt)
            except ValueError:
                continue
    return None
