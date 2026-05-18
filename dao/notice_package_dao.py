"""notice_packages 表的数据访问对象（SQLAlchemy 2.0）."""

import logging
from decimal import Decimal
from typing import List

from sqlalchemy import delete

from model import NoticePackage

from .base import session_scope, _to_decimal, parse_amount

logger = logging.getLogger(__name__)


class NoticePackageDao:
    """公告分包表存储器."""

    def insert(self, notice_id: int, packages: List[dict]) -> int:
        """插入公告分包，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            packages: LLM 解析出的分包列表

        Returns:
            插入条数
        """
        if not packages:
            return 0

        records = []
        for item in packages:
            if not isinstance(item, dict):
                continue
            records.append(
                NoticePackage(
                    notice_id=notice_id,
                    no=str(item.get("no") or "")[:16],
                    name=str(item.get("name") or "")[:256],
                    budget=parse_amount(item.get("budge") or item.get("budget") or "") or Decimal("0.00"),
                    max_limit=parse_amount(item.get("max_limit") or "") or Decimal("0.00"),
                    quantity=_to_decimal(item.get("quantity")),
                    unit=str(item.get("unit") or "")[:32],
                )
            )

        if not records:
            return 0

        with session_scope() as session:
            session.execute(
                delete(NoticePackage).where(NoticePackage.notice_id == notice_id)
            )
            session.add_all(records)
            session.commit()
            return len(records)
