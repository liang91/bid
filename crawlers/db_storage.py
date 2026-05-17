"""MySQL 数据库存储模块 — 写入 procurement_notices 表."""

import json
import re
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional

import pymysql
from pymysql.cursors import DictCursor

from .config_loader import load_config
from .models import ProcurementNotice

# 加载配置（模块级缓存）
_cfg = None


def _get_db_config():
    global _cfg
    if _cfg is None:
        try:
            _cfg = load_config()
        except FileNotFoundError:
            _cfg = {}
    return _cfg


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
            host: Optional[str] = None,
            port: Optional[int] = None,
            user: Optional[str] = None,
            password: Optional[str] = None,
            database: Optional[str] = None,
            charset: Optional[str] = None,
    ):
        cfg = _get_db_config()

        self.conn_params = {
            "host": host or cfg.get("mysql.host") or "localhost",
            "port": port if port is not None else cfg.get("mysql.port", 3306),
            "user": user or cfg.get("mysql.user") or "root",
            "password": password if password is not None else cfg.get("mysql.password", ""),
            "database": database or cfg.get("mysql.database") or "bid",
            "charset": charset or cfg.get("mysql.charset") or "utf8mb4",
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

    @staticmethod
    def _quote_field(name: str) -> str:
        """给 SQL 字段名加反引号，避免与保留关键字冲突."""
        return f"`{name}`"

    def _build_insert_sql(self) -> str:
        """构建 INSERT ... ON DUPLICATE KEY UPDATE 语句."""
        fields = [
            "platform", "part", "title", "notice_type", "url",
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
            "abstract", "html", "parse_time",
            "status", "created_at", "updated_at",
        ]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        # ON DUPLICATE KEY UPDATE: 排除 auto_increment 和 created_at
        updates = ", ".join([f"{self._quote_field(f)}=VALUES({self._quote_field(f)})" for f in fields if f not in ("created_at",)])
        return (
            f"INSERT INTO procurement_notices ({columns}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )

    @staticmethod
    def _is_open_tender(notice: ProcurementNotice) -> bool:
        """判断公告是否为公开招标类型（入库前严格校验）."""
        if not notice.notice_type:
            return False
        nt = notice.notice_type.strip()
        if "公开招标" not in nt:
            return False
        exclude_keywords = ("中标", "成交", "结果", "更正", "废标", "终止")
        if any(kw in nt for kw in exclude_keywords):
            return False
        return True

    def save_notices(self, notices: List[ProcurementNotice], batch_size: int = 100) -> dict:
        """批量保存公告到 MySQL procurement_notices 表，自动去重（基于 URL）并更新已存在记录.

        仅保存 notice_type 包含"公开招标"的公告，其他类型自动过滤。

        Args:
            notices: 招标公告列表
            batch_size: 每批插入数量

        Returns:
            {"inserted": int, "updated": int, "failed": int, "skipped": int}
        """
        if not notices:
            return {"inserted": 0, "updated": 0, "failed": 0, "skipped": 0}

        # 入库前严格过滤：仅保留公开招标
        original_count = len(notices)
        notices = [n for n in notices if self._is_open_tender(n)]
        skipped = original_count - len(notices)
        if skipped > 0:
            print(f"[MySQLStorage] 过滤非公开招标 {skipped} 条，实际入库 {len(notices)} 条")

        inserted = updated = failed = 0
        batches = [
            notices[i: i + batch_size] for i in range(0, len(notices), batch_size)
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

        return {"inserted": inserted, "updated": updated, "failed": failed, "skipped": skipped}

    def _find_existing(self, cursor, urls: List[str]) -> set:
        """查询给定的 URL 中哪些已经存在."""
        if not urls:
            return set()
        existing = set()
        batch_size = 500
        for i in range(0, len(urls), batch_size):
            batch = urls[i: i + batch_size]
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

    def dedup_by_url(self, notices: List[ProcurementNotice]) -> List[ProcurementNotice]:
        """基于数据库已有 URL 去重，返回尚未入库的公告."""
        if not notices:
            return []

        urls = [n.url for n in notices if n.url]
        if not urls:
            return notices

        with self._get_cursor() as cursor:
            existing = self._find_existing(cursor, urls)

        return [n for n in notices if n.url not in existing]

    # ---------------------------------------------------------------------------
    # 分步存储方法（fetch_list / fetch_html / parse_detail 专用）
    # ---------------------------------------------------------------------------

    def insert_list_notices(self, notices: List[ProcurementNotice], batch_size: int = 100) -> dict:
        """仅插入列表页获取到的公告（INSERT IGNORE，不更新已有记录）.

        适用于 fetch_list 阶段，状态默认为 1（获取概要信息）。
        已存在（基于 URL 唯一键）的记录会被自动忽略。

        Returns:
            {"inserted": int, "skipped": int}
        """
        if not notices:
            return {"inserted": 0, "skipped": 0}

        # 使用 INSERT IGNORE，基于 url 唯一键跳过已存在记录
        fields = [
            "platform", "part", "title", "notice_type", "url", "region_province",
            "method", "notice_date", "purchaser_name", "status", "created_at", "updated_at",
        ]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        sql = f"INSERT IGNORE INTO procurement_notices ({columns}) VALUES ({placeholders})"

        inserted = 0
        batches = [notices[i: i + batch_size] for i in range(0, len(notices), batch_size)]
        with self._get_cursor() as cursor:
            for batch in batches:
                params = [self._notice_to_dict(n) for n in batch]
                try:
                    cursor.executemany(sql, params)
                    inserted += cursor.rowcount
                except Exception as e:
                    print(f"[MySQLStorage] 列表页批量插入失败: {e}")

        skipped = len(notices) - inserted
        return {"inserted": inserted, "skipped": skipped}

    def fetch_by_status(self, status: int, platform: str, limit: int = 100, ) -> List[ProcurementNotice]:
        """按爬取状态查询公告记录，可额外按平台筛选.

        Args:
            status: 1=获取概要信息, 20=获取了网页内容, 30=解析出了公告内容
            limit: 最大返回条数
            platform: 平台名称（如"中国政府采购网"），为 None 则不限制平台

        Returns:
            ProcurementNotice 列表
        """
        sql = """
                SELECT * FROM procurement_notices
                WHERE status = %s AND platform = %s
                ORDER BY id ASC
                LIMIT %s
            """
        params = (status, platform, limit)

        with self._get_cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [self._row_to_notice(row) for row in rows]

    def update_html_content(self, notice_id: int, html: str) -> bool:
        """更新详情页 HTML 内容，并将状态推进到 20.

        Args:
            notice_id: 公告记录 ID
            html: 详情页原始 HTML

        Returns:
            是否更新成功
        """
        sql = """
            UPDATE procurement_notices
            SET html = %s, status = 20, updated_at = NOW()
            WHERE id = %s
        """
        with self._get_cursor() as cursor:
            cursor.execute(sql, (html, notice_id))
            return cursor.rowcount > 0

    def update_parsed_detail(self, notice: ProcurementNotice) -> bool:
        """更新 LLM 解析后的详情字段，并将状态推进到 30.

        Args:
            notice: 已填充解析结果的 ProcurementNotice 实例（必须包含 id）

        Returns:
            是否更新成功
        """
        if not notice.id:
            print("[MySQLStorage] update_parsed_detail 失败: notice.id 为空")
            return False

        update_fields = [
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
            "abstract", "parse_time",
            "status", "updated_at",
        ]

        d = self._notice_to_dict(notice)
        set_clause = ", ".join([f"{self._quote_field(f)} = %({f})s" for f in update_fields])
        sql = f"UPDATE procurement_notices SET {set_clause} WHERE id = %(id)s"

        params = {f: d[f] for f in update_fields}
        params["id"] = notice.id

        with self._get_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount > 0

    # -------------------------------------------------------------------------
    # 子表插入方法（parse_detail 阶段调用）
    # -------------------------------------------------------------------------

    def insert_notice_attachments(self, notice_id: int, attachments: list) -> int:
        """插入公告附件，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            attachments: LLM 解析出的附件列表，元素格式 {"name": ..., "url": ...}

        Returns:
            插入条数
        """
        if not attachments:
            return 0

        sql_delete = "DELETE FROM notice_attachments WHERE notice_id = %s"

        fields = ["notice_id", "name", "download_url"]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        sql_insert = f"INSERT INTO notice_attachments ({columns}) VALUES ({placeholders})"

        params = []
        for item in attachments:
            if not isinstance(item, dict):
                continue
            params.append({
                "notice_id": notice_id,
                "name": str(item.get("name") or "")[:256],
                "download_url": str(item.get("url") or "")[:512],
            })

        if not params:
            return 0

        with self._get_cursor() as cursor:
            cursor.execute(sql_delete, (notice_id,))
            cursor.executemany(sql_insert, params)
            return cursor.rowcount

    def insert_notice_packages(self, notice_id: int, packages: list) -> int:
        """插入公告分包，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            packages: LLM 解析出的分包列表，元素格式 {"no": ..., "name": ..., "budge": ..., ...}

        Returns:
            插入条数
        """
        if not packages:
            return 0

        sql_delete = "DELETE FROM notice_packages WHERE notice_id = %s"

        fields = ["notice_id", "no", "name", "budget", "max_limit", "quantity", "unit"]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        sql_insert = f"INSERT INTO notice_packages ({columns}) VALUES ({placeholders})"

        params = []
        for item in packages:
            if not isinstance(item, dict):
                continue
            params.append({
                "notice_id": notice_id,
                "no": str(item.get("no") or "")[:16],
                "name": str(item.get("name") or "")[:256],
                "budget": _to_decimal(parse_amount(item.get("budge") or item.get("budget") or "")),
                "max_limit": _to_decimal(parse_amount(item.get("max_limit") or "")),
                "quantity": _to_decimal(item.get("quantity") or 0),
                "unit": str(item.get("unit") or "")[:32],
            })

        if not params:
            return 0

        with self._get_cursor() as cursor:
            cursor.execute(sql_delete, (notice_id,))
            cursor.executemany(sql_insert, params)
            return cursor.rowcount

    def insert_notice_qualifications(self, notice_id: int, qualifications: list) -> int:
        """插入公告资质要求，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            qualifications: LLM 解析出的资质列表

        Returns:
            插入条数
        """
        if not qualifications:
            return 0

        sql_delete = "DELETE FROM notice_qualifications WHERE notice_id = %s"

        fields = [
            "notice_id", "qualification_type", "name", "required_scope",
            "valid_required", "evidence_type", "joint_bid_acceptable", "sort_order",
        ]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        sql_insert = f"INSERT INTO notice_qualifications ({columns}) VALUES ({placeholders})"

        params = []
        for idx, item in enumerate(qualifications):
            if not isinstance(item, dict):
                continue
            params.append({
                "notice_id": notice_id,
                "qualification_type": str(item.get("qualification_type") or "")[:32],
                "name": str(item.get("name") or "")[:128],
                "required_scope": str(item.get("required_scope") or "")[:256],
                "valid_required": _to_tinyint(item.get("valid_required")),
                "evidence_type": str(item.get("evidence_type") or "")[:64],
                "joint_bid_acceptable": _to_tinyint(item.get("joint_bid_acceptable")),
                "sort_order": idx,
            })

        if not params:
            return 0

        with self._get_cursor() as cursor:
            cursor.execute(sql_delete, (notice_id,))
            cursor.executemany(sql_insert, params)
            return cursor.rowcount

    @staticmethod
    def _row_to_notice(row: dict) -> ProcurementNotice:
        """将数据库查询结果行转换为 ProcurementNotice 实例."""
        notice = ProcurementNotice()

        # 基础字段：模型字段名和数据库列名一致时直接赋值
        for key, val in row.items():
            if not hasattr(notice, key):
                continue
            if val is None:
                continue

            # JSON 字段反序列化
            if key in ("industry_tags", "keywords", "suggested_company_types"):
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        val = []
                elif not isinstance(val, list):
                    val = []

            # 整数字段
            if key in ("id", "status", "joint_bid_allowed", "joint_bid_max_members",
                       "sme_oriented", "ca_required"):
                val = int(val) if val is not None else 0

            setattr(notice, key, val)

        # 数据库 html 映射到模型的 html 字段
        if row.get("html"):
            notice.html = row["html"]

        return notice

    @staticmethod
    def _notice_to_dict(notice: ProcurementNotice) -> dict:
        """将 ProcurementNotice 转换为可插入 procurement_notices 的字典.

        字段名已与 SQL 表一一对应，仅需做类型转换：
        - 金额字符串 → Decimal
        - 时间字符串 → datetime
        - list → JSON 字符串（或 None）
        """
        d = notice.to_dict()

        # JSON 字段转换
        def _to_json(val):
            if val and isinstance(val, list) and len(val) > 0:
                return json.dumps(val, ensure_ascii=False)
            return None

        result = {
            "platform": d.get("platform") or "中国政府采购网",
            "part": d.get("part") or "",
            "title": d.get("title") or d.get("project_name") or "",
            "notice_type": d.get("notice_type") or "",
            "url": d.get("url") or "",

            "region_province": d.get("region_province") or "",
            "region_city": d.get("region_city") or "",
            "region_district": d.get("region_district") or "",

            "project_name": d.get("project_name") or d.get("title") or "",
            "project_no": d.get("project_no") or "",
            "purchase_plan_no": d.get("purchase_plan_no") or "",

            "budget": _to_decimal(parse_amount(d.get("budget"))),
            "max_limit": _to_decimal(parse_amount(d.get("max_limit"))),
            "currency": d.get("currency") or "CNY",

            "category_code": d.get("category_code") or "",
            "category_name": d.get("category_name") or "",

            "method": d.get("method") or d.get("notice_type") or "",
            "joint_bid_allowed": d.get("joint_bid_allowed") or 0,
            "joint_bid_max_members": d.get("joint_bid_max_members") or 1,
            "sme_oriented": d.get("sme_oriented") or 0,

            "notice_date": _to_datetime(parse_chinese_datetime(d.get("notice_date"))),
            "doc_obtain_start": _to_datetime(parse_chinese_datetime(d.get("doc_obtain_start"))),
            "doc_obtain_end": _to_datetime(parse_chinese_datetime(d.get("doc_obtain_end"))),
            "bid_deadline": _to_datetime(parse_chinese_datetime(d.get("bid_deadline"))),
            "bid_open_time": _to_datetime(parse_chinese_datetime(d.get("bid_open_time"))),

            "bid_platform": d.get("bid_platform") or "",
            "bid_platform_url": d.get("bid_platform_url") or "",
            "ca_required": d.get("ca_required") or 0,
            "doc_price": _to_decimal(parse_amount(d.get("doc_price"))),

            "purchaser_name": d.get("purchaser_name") or d.get("purchaser") or "",
            "purchaser_address": d.get("purchaser_address") or "",
            "purchaser_contact_person": d.get("purchaser_contact_person") or "",
            "purchaser_contact_phone": d.get("purchaser_contact_phone") or "",
            "purchaser_region": d.get("purchaser_region") or d.get("region") or "",

            "agency_name": d.get("agency_name") or "",
            "agency_address": d.get("agency_address") or "",
            "agency_contact_person": d.get("agency_contact_person") or "",
            "agency_contact_phone": d.get("agency_contact_phone") or "",
            "agency_region": d.get("agency_region") or "",

            "project_contact_person": d.get("project_contact_person") or "",
            "project_contact_phone": d.get("project_contact_phone") or "",

            "qualification_summary": d.get("qualification_summary") or None,
            "industry_tags": _to_json(d.get("industry_tags")),
            "keywords": _to_json(d.get("keywords")),
            "suggested_company_types": _to_json(d.get("suggested_company_types")),
            "geographic_advantage": d.get("geographic_advantage") or "",

            "abstract": d.get("abstract") or "",
            "html": d.get("html") or "",
            "parse_time": datetime.now(),

            "status": d.get("status") or 1,
            "created_at": _parse_crawled_at(d.get("created_at")),
            "updated_at": datetime.now(),
        }

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


def _to_tinyint(val) -> int:
    """将解析结果转为 0/1 的 TINYINT，支持布尔/字符串/数字."""
    if val is None:
        return 0
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, (int, float)):
        return 1 if val else 0
    s = str(val).strip().lower()
    return 1 if s in ("1", "true", "是", "yes", "y") else 0


# DATETIME NOT NULL 字段的默认值（与数据库默认值保持一致）
_DEFAULT_DATETIME = datetime(1970, 1, 1, 0, 0, 0)


def _to_datetime(val) -> datetime:
    """将解析结果转为 datetime，None 则返回数据库默认值 1970-01-01 00:00:00."""
    if val is None:
        return _DEFAULT_DATETIME
    if isinstance(val, datetime):
        return val.replace(tzinfo=None) if val.tzinfo else val
    return _DEFAULT_DATETIME


def _parse_crawled_at(crawled) -> datetime:
    """将 crawled_at 转为 datetime，解析失败返回当前时间."""
    if isinstance(crawled, str):
        try:
            return datetime.fromisoformat(crawled.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.now()
    elif isinstance(crawled, datetime):
        return crawled.replace(tzinfo=None) if crawled.tzinfo else crawled
    return datetime.now()


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
                return datetime.strptime(
                    m.group(0).replace("/", "-").replace("年", "-").replace("月", "-").replace("日", ""), fmt)
            except ValueError:
                continue
    return None
