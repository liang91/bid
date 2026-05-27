"""notice_attachments 表的数据访问对象（SQLAlchemy 2.0）."""

from typing import List

from sqlalchemy import delete
from models import NoticeAttachment, NoticeAttachmentDto
from dao import db


class NoticeAttachmentDao:
    """公告附件表存储器."""

    @staticmethod
    def insert(notice_id: int, attachments: List[NoticeAttachmentDto]) -> int:
        """插入公告附件，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            attachments: 附件 DTO 列表

        Returns:
            插入条数
        """
        if not attachments:
            return 0

        records = []
        for dto in attachments:
            records.append(
                NoticeAttachment(
                    notice_id=notice_id,
                    name=dto.name,
                    url=dto.url,
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
