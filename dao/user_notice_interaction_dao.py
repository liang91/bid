"""user_notice_interactions 表的数据访问对象."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, insert
from sqlalchemy.dialects.mysql import insert as mysql_insert

from dao import db
from models import UserNoticeInteraction, UserNoticeInteractionDto


class UserNoticeInteractionDao:
    """用户-公告互动存储器."""

    @staticmethod
    def get(user_id: int, notice_id: int) -> Optional[UserNoticeInteractionDto]:
        """查询单条互动记录."""
        with db() as session:
            stmt = (
                select(UserNoticeInteraction)
                .where(UserNoticeInteraction.user_id == user_id)
                .where(UserNoticeInteraction.notice_id == notice_id)
            )
            obj = session.execute(stmt).scalar_one_or_none()
            if not obj:
                return None
            return UserNoticeInteractionDto.model_validate(obj)

    @staticmethod
    def upsert_favorite(user_id: int, notice_id: int, is_favorite: int) -> bool:
        """收藏/取消收藏."""
        with db.begin() as session:
            stmt = (
                mysql_insert(UserNoticeInteraction)
                .values(
                    user_id=user_id,
                    notice_id=notice_id,
                    is_favorite=is_favorite,
                    favorited_at=datetime.now() if is_favorite else None,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                .on_duplicate_key_update(
                    is_favorite=is_favorite,
                    favorited_at=datetime.now() if is_favorite else None,
                    updated_at=datetime.now(),
                )
            )
            session.execute(stmt)
            return True

    @staticmethod
    def upsert_not_interested(user_id: int, notice_id: int) -> bool:
        """标记不感兴趣."""
        with db.begin() as session:
            stmt = (
                mysql_insert(UserNoticeInteraction)
                .values(
                    user_id=user_id,
                    notice_id=notice_id,
                    is_not_interested=1,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                .on_duplicate_key_update(
                    is_not_interested=1,
                    updated_at=datetime.now(),
                )
            )
            session.execute(stmt)
            return True

    @staticmethod
    def mark_viewed(user_id: int, notice_id: int) -> bool:
        """标记已浏览."""
        with db.begin() as session:
            stmt = (
                mysql_insert(UserNoticeInteraction)
                .values(
                    user_id=user_id,
                    notice_id=notice_id,
                    is_viewed=1,
                    viewed_at=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                .on_duplicate_key_update(
                    is_viewed=1,
                    viewed_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            session.execute(stmt)
            return True

    @staticmethod
    def fetch_favorites(user_id: int, limit: int = 100, offset: int = 0) -> list[UserNoticeInteractionDto]:
        """获取用户的收藏列表."""
        with db() as session:
            stmt = (
                select(UserNoticeInteraction)
                .where(UserNoticeInteraction.user_id == user_id)
                .where(UserNoticeInteraction.is_favorite == 1)
                .order_by(UserNoticeInteraction.favorited_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [UserNoticeInteractionDto.model_validate(row) for row in rows]

    @staticmethod
    def fetch_interactions(user_id: int, notice_ids: list[int]) -> dict[int, UserNoticeInteractionDto]:
        """批量查询用户与一批公告的互动状态."""
        if not notice_ids:
            return {}
        with db() as session:
            stmt = (
                select(UserNoticeInteraction)
                .where(UserNoticeInteraction.user_id == user_id)
                .where(UserNoticeInteraction.notice_id.in_(notice_ids))
            )
            rows = session.execute(stmt).scalars().all()
            return {row.notice_id: UserNoticeInteractionDto.model_validate(row) for row in rows}
