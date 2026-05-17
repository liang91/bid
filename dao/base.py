"""DAO 基类与公共工具函数."""

import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import pymysql
from pymysql.cursors import DictCursor

from config import load_config

logger = logging.getLogger(__name__)

# 加载配置（模块级缓存）
_cfg = None


def get_db_config():
    """加载并返回数据库配置字典（模块级缓存）."""
    global _cfg
    if _cfg is None:
        try:
            _cfg = load_config()
        except FileNotFoundError:
            _cfg = {}
    return _cfg


class BaseStorage:
    """数据库存储基类，接收已初始化好的连接参数，提供通用游标上下文管理器."""

    _instances = {}

    def __init__(self, conn_params: dict):
        self.conn_params = conn_params

    @classmethod
    def instance(cls, conn_params=None):
        """获取单例实例；首次调用时自动使用默认配置初始化."""
        if cls not in BaseStorage._instances:
            if conn_params is None:
                from dao import _CONN_PARAMS
                conn_params = _CONN_PARAMS
            BaseStorage._instances[cls] = cls(conn_params)
        return BaseStorage._instances[cls]

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
    re.compile(r"[￥¥]?\s*([\d,.]+)\s*万\s*元"),
    re.compile(r"[￥¥]?\s*([\d,.]+)\s*元"),
    re.compile(r"^\s*([\d,.]+)\s*$"),
]


def parse_amount(text: Optional[str]) -> Optional[Decimal]:
    """将中文金额字符串解析为以【元】为单位的 Decimal."""
    if not text:
        return None

    text = text.strip()
    if not text or text in ("-", "—", "无", "null", "NULL"):
        return None

    m = _AMOUNT_PATTERNS[0].search(text)
    if m:
        try:
            num = Decimal(m.group(1).replace(",", ""))
            return (num * 10000).quantize(Decimal("0.0001"))
        except InvalidOperation:
            pass

    m = _AMOUNT_PATTERNS[1].search(text)
    if m:
        try:
            return Decimal(m.group(1).replace(",", "")).quantize(Decimal("0.0001"))
        except InvalidOperation:
            pass

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
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})"), "%Y-%m-%d %H:%M"),
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})"), "%Y-%m-%d %H:%M"),
    (re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})"), "%Y-%m-%d %H:%M"),
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"), "%Y-%m-%d"),
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
