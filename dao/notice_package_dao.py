"""notice_packages 表的数据访问对象."""

import logging
from typing import List

from .base import BaseStorage, _to_decimal, parse_amount

logger = logging.getLogger(__name__)


class NoticePackageDao(BaseStorage):
    """公告分包表存储器."""

    def __init__(self, conn_params: dict):
        super().__init__(conn_params)

    def insert(self, notice_id: int, packages: List[dict]) -> int:
        """插入公告分包，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            packages: LLM 解析出的分包列表，元素格式 {"no": ..., "name": ..., "budget": ..., ...}

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
