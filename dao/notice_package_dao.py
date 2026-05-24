"""notice_packages 表的数据访问对象（SQLAlchemy 2.0）."""

from typing import List

from loguru import logger

from sqlalchemy import delete
from model import NoticePackage
from model.notice_package import NoticePackageDto

from dao import db



class NoticePackageDao:
    """公告分包表存储器."""

    @staticmethod
    def insert(notice_id: int, packages: List[NoticePackageDto]) -> int:
        """插入公告分包，先删除旧记录再批量插入.

        Args:
            notice_id: 关联公告ID
            packages: 分包 DTO 列表

        Returns:
            插入条数
        """
        if not packages:
            return 0

        records = []
        for dto in packages:
            records.append(
                NoticePackage(
                    notice_id=notice_id,
                    no=dto.no,
                    name=dto.name,
                    budget=dto.budget,
                    quantity=dto.quantity,
                    unit=dto.unit,
                )
            )

        if not records:
            return 0

        with db.begin() as session:
            stmt = delete(NoticePackage).where(NoticePackage.notice_id == notice_id)
            session.execute(stmt)
            session.add_all(records)
            return len(records)
