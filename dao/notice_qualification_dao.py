"""notice_qualifications 表的数据访问对象（SQLAlchemy 2.0）."""

import logging
from typing import List

from sqlalchemy import delete

from model import NoticeQualification

from dao import db

logger = logging.getLogger(__name__)


class NoticeQualificationDao:
    """公告资质要求表存储器."""

    @staticmethod
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

        records = []
        for idx, item in enumerate(qualifications):
            if not isinstance(item, dict):
                continue
            records.append(
                NoticeQualification(
                    notice_id=notice_id,
                    qualification_type=str(item.get("qualification_type") or "")[:32],
                    name=str(item.get("name") or "")[:128],
                    required_scope=str(item.get("required_scope") or "")[:256],
                    valid_required=_to_tinyint(item.get("valid_required")),
                    evidence_type=str(item.get("evidence_type") or "")[:64],
                    joint_bid_acceptable=_to_tinyint(item.get("joint_bid_acceptable")),
                    sort_order=idx,
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
