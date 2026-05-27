"""notices 表的数据访问对象（SQLAlchemy 2.0）."""

from datetime import datetime
from typing import List, Optional
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert
from models import Notice, NoticeDto
from dao import db, orm_to_dto


class NoticeDao:
    """招标公告主表存储器."""

    @staticmethod
    def get_by_id(id: int) -> Optional[NoticeDto]:
        """根据公告ID查询."""
        with db() as session:
            obj = session.get(Notice, id)
            if not obj:
                return None
            return orm_to_dto(obj, NoticeDto)

    # -----------------------------------------------------------------------
    # 批量保存（INSERT ... ON DUPLICATE KEY UPDATE）
    # -----------------------------------------------------------------------
    @staticmethod
    def create(notices: list[NoticeDto]) -> bool:
        """批量保存公告，自动去重（基于 URL）并更新已存在记录"""
        datas = [notice.model_dump(exclude={"id", "created_at", "updated_at"}) for notice in notices]
        with db.begin() as session:
            stmt = insert(Notice).values(datas)
            session.execute(stmt)

        return True

    # -----------------------------------------------------------------------
    # Embedding 更新（supplier_profile_embedding BLOB 字段）
    # -----------------------------------------------------------------------
    @staticmethod
    def update_supplier_profile_embedding(notice_id: int, embedding: bytes) -> bool:
        """更新公告的 supplier_profile_embedding 向量（BLOB 存储）."""
        with db.begin() as session:
            notice = session.get(Notice, notice_id)
            if not notice:
                return False
            notice.supplier_profile_embedding = embedding
            return True

    # -----------------------------------------------------------------------
    # 粗筛查询（硬规则）
    # -----------------------------------------------------------------------
    @staticmethod
    def fetch_candidates_for_matching(
            region_names: list,
            min_budget: float,
            max_budget: float,
            limit: int = 25,
    ) -> list[NoticeDto]:
        """硬规则粗筛：根据地域、预算、采购方式、排除项、CA/中小企业、时效性筛选公告."""
        stmt = select(Notice).where(
            Notice.status == 30,
            Notice.bid_deadline > func.now(),
            Notice.region_province.in_(region_names),
            Notice.budget >= min_budget,
            Notice.budget <= max_budget,
        )
        stmt = stmt.order_by(Notice.notice_date.desc()).limit(limit)

        with db() as session:
            result = session.execute(stmt)
            return [orm_to_dto(row, NoticeDto) for row in result.scalars().all()]

    # -----------------------------------------------------------------------
    # URL 存在性检查
    # -----------------------------------------------------------------------
    @staticmethod
    def exists(url: str) -> bool:
        """检查 URL 是否已存在."""
        with db.begin() as session:
            result = session.execute(
                select(Notice.id).where(Notice.url == url).limit(1)
            )
            return result.scalar() is not None

    # -----------------------------------------------------------------------
    # URL 去重
    # -----------------------------------------------------------------------
    @staticmethod
    def dedup_by_url(notices: List[NoticeDto]) -> List[NoticeDto]:
        """基于数据库已有 URL 去重，返回尚未入库的公告."""
        if not notices:
            return []

        urls = [dto.url for dto in notices if dto.url]
        if not urls:
            return notices

        with db() as session:
            existing = session.execute(
                select(Notice.url).where(Notice.url.in_(urls))
            ).scalars().all()
            existing_set = set(existing)

        return [dto for dto in notices if dto.url not in existing_set]

    # -----------------------------------------------------------------------
    # 按状态查询
    # -----------------------------------------------------------------------
    @staticmethod
    def fetch_by_status(status: int, platform: str, limit: int = 100) -> List[NoticeDto]:
        """按爬取状态查询公告记录."""
        with db() as session:
            result = session.execute(
                select(Notice)
                .where(Notice.status == status, Notice.platform == platform)
                .order_by(Notice.id.asc())
                .limit(limit)
            )
            return [orm_to_dto(row, NoticeDto) for row in result.scalars().all()]

    # -----------------------------------------------------------------------
    # 更新 HTML
    # -----------------------------------------------------------------------
    @staticmethod
    def update_html(notice_id: int, html: str) -> bool:
        """保存html文件路径，并将状态推进到 20."""
        with db.begin() as session:
            notice = session.get(Notice, notice_id)
            if not notice:
                return False
            notice.html = html
            notice.status = 20
            notice.updated_at = datetime.now()
            return True

    # -----------------------------------------------------------------------
    # 更新解析结果
    # -----------------------------------------------------------------------
    @staticmethod
    def update_parsed(dto: NoticeDto) -> bool:
        """更新 LLM 解析后的详情字段，并将状态推进到 30"""
        if not dto.id:
            logger.error("[NoticeDao] update_parsed 失败: dto.id 为空")
            return False

        with db.begin() as session:
            notice = session.get(Notice, dto.id)
            if not notice:
                logger.error(f"[NoticeDao] update_parsed 失败: id={dto.id} 不存在")
                return False

            for key, value in dto.model_dump(exclude={"id", "created_at"}).items():
                setattr(notice, key, value)

            notice.status = 30
            notice.updated_at = datetime.now()
            return True
