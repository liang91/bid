"""notice_qualifications 表的数据访问对象（SQLAlchemy 2.0）."""

from typing import List

from loguru import logger

from sqlalchemy import delete
from model import NoticeQualification
from model.notice_qualification import NoticeQualificationDto

from dao import db



class NoticeQualificationDao:
    """公告资质要求表存储器."""

    @staticmethod
    def insert(notice_id: int, qualifications: List[NoticeQualificationDto]) -> int:
        """插入公告资质要求，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            qualifications: 资质要求 DTO 列表

        Returns:
            插入条数
        """
        if not qualifications:
            return 0

        records = []
        for dto in qualifications:
            records.append(
                NoticeQualification(
                    notice_id=notice_id,
                    qualification_type=dto.qualification_type,
                    name=dto.name,
                )
            )

        if not records:
            return 0

        with db.begin() as session:
            session.execute(
                delete(NoticeQualification).where(
                    NoticeQualification.notice_id == notice_id
                )
            )
            session.add_all(records)
            return len(records)
