"""notice_attachments 表的数据访问对象（SQLAlchemy 2.0）."""

import logging

from sqlalchemy import delete

from model import NoticeAttachment

from dao import db

logger = logging.getLogger(__name__)


class NoticeAttachmentDao:
    """公告附件表存储器."""

    @staticmethod
    def insert(notice_id: int, attachments: list[dict]) -> int:
        """插入公告附件，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            attachments: LLM 解析出的附件列表，元素格式 {"name": ..., "url": ...}

        Returns:
            插入条数
        """
        if not attachments:
            return 0

        records = []
        for item in attachments:
            if not isinstance(item, dict):
                continue
            records.append(
                NoticeAttachment(
                    notice_id=notice_id,
                    name=str(item.get("name") or "")[:256],
                    url=str(item.get("url") or "")[:512],
                )
            )

        if not records:
            return 0

        with db.begin() as session:
            session.execute(
                delete(NoticeAttachment).where(NoticeAttachment.notice_id == notice_id)
            )
            session.add_all(records)
            return len(records)
