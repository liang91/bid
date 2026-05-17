"""notice_attachments 表的数据访问对象."""

import logging
from typing import List

from .base import BaseStorage

logger = logging.getLogger(__name__)


class NoticeAttachmentDao(BaseStorage):
    """公告附件表存储器."""

    def __init__(self, conn_params: dict):
        super().__init__(conn_params)

    def insert(self, notice_id: int, attachments: List[dict]) -> int:
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

        fields = ["notice_id", "name", "url"]
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
                "url": str(item.get("url") or "")[:512],
            })

        if not params:
            return 0

        with self._get_cursor() as cursor:
            cursor.execute(sql_delete, (notice_id,))
            cursor.executemany(sql_insert, params)
            return cursor.rowcount
