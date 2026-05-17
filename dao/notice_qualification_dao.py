"""notice_qualifications 表的数据访问对象."""

import logging
from typing import List

from .base import BaseStorage, _to_tinyint

logger = logging.getLogger(__name__)


class NoticeQualificationDao(BaseStorage):
    """公告资质要求表存储器."""

    def __init__(self, conn_params: dict):
        super().__init__(conn_params)

    def insert(self, notice_id: int, qualifications: List[dict]) -> int:
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
