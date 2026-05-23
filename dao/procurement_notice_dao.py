"""procurement_notices 表的数据访问对象（SQLAlchemy 2.0）."""

from datetime import datetime
from typing import List, Optional

from loguru import logger

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert

from model import ProcurementNotice
from model.procurement_notice import ProcurementNoticeDto

from dao import db, orm_to_dto


class ProcurementNoticeDao:
    """招标公告主表存储器."""

    @staticmethod
    def get_by_id(id: int) -> Optional[ProcurementNoticeDto]:
        """根据公告ID查询."""
        with db() as session:
            obj = session.get(ProcurementNotice, id)
            if not obj:
                return None
            return orm_to_dto(obj, ProcurementNoticeDto)

    # -----------------------------------------------------------------------
    # 批量保存（INSERT ... ON DUPLICATE KEY UPDATE）
    # -----------------------------------------------------------------------
    @staticmethod
    def save(notices: list[ProcurementNoticeDto]) -> bool:
        """批量保存公告，自动去重（基于 URL）并更新已存在记录"""
        datas = [notice.model_dump(exclude={"id", "created_at", "updated_at"}) for notice in notices]
        with db.begin() as session:
            stmt = insert(ProcurementNotice).values(datas)
            session.execute(stmt)

        return True

    # -----------------------------------------------------------------------
    # Embedding 更新
    # -----------------------------------------------------------------------
    @staticmethod
    def update_embedding(notice_id: int, embedding: list) -> bool:
        """更新公告的 Embedding 向量."""
        with db.begin() as session:
            notice = session.get(ProcurementNotice, notice_id)
            if not notice:
                return False
            notice.category_embedding = embedding
            return True

    # -----------------------------------------------------------------------
    # 粗筛查询（硬规则）
    # -----------------------------------------------------------------------
    @staticmethod
    def fetch_candidates_for_matching(
            region_names: list,
            min_budget: float,
            max_budget: float,
            preferred_methods: list,
            excluded_keywords: list,
            sme_status: int,
            ca_ready: int,
            limit: int = 2000,
    ) -> List[ProcurementNoticeDto]:
        """硬规则粗筛：根据地域、预算、采购方式、排除项、CA/中小企业、时效性筛选公告."""
        if not region_names:
            return []

        stmt = select(ProcurementNotice).where(
            ProcurementNotice.status == 30,
            ProcurementNotice.bid_deadline > func.now(),
            ProcurementNotice.region_province.in_(region_names),
            ProcurementNotice.budget >= min_budget,
            ProcurementNotice.budget <= max_budget,
        )

        if preferred_methods:
            stmt = stmt.where(ProcurementNotice.method.in_(preferred_methods))

        for kw in excluded_keywords:
            if kw.strip():
                like_pattern = f"%{kw.strip()}%"
                stmt = stmt.where(
                    ProcurementNotice.title.not_like(like_pattern),
                    ProcurementNotice.project_name.not_like(like_pattern),
                    ProcurementNotice.abstract.not_like(like_pattern),
                )

        stmt = stmt.where(
            (ProcurementNotice.sme_oriented == 0) | (sme_status == 1),
            (ProcurementNotice.ca_required == 0) | (ca_ready == 1),
        )

        stmt = stmt.order_by(ProcurementNotice.notice_date.desc()).limit(limit)

        with db.begin() as session:
            result = session.execute(stmt)
            return [orm_to_dto(row, ProcurementNoticeDto) for row in result.scalars().all()]

    # -----------------------------------------------------------------------
    # URL 存在性检查
    # -----------------------------------------------------------------------
    @staticmethod
    def exists(url: str) -> bool:
        """检查 URL 是否已存在."""
        with db.begin() as session:
            result = session.execute(
                select(ProcurementNotice.id).where(ProcurementNotice.url == url).limit(1)
            )
            return result.scalar() is not None

    # -----------------------------------------------------------------------
    # URL 去重
    # -----------------------------------------------------------------------
    @staticmethod
    def dedup_by_url(notices: List[ProcurementNoticeDto]) -> List[ProcurementNoticeDto]:
        """基于数据库已有 URL 去重，返回尚未入库的公告."""
        if not notices:
            return []

        urls = [dto.url for dto in notices if dto.url]
        if not urls:
            return notices

        with db() as session:
            existing = session.execute(
                select(ProcurementNotice.url).where(ProcurementNotice.url.in_(urls))
            ).scalars().all()
            existing_set = set(existing)

        return [dto for dto in notices if dto.url not in existing_set]

    # -----------------------------------------------------------------------
    # 按状态查询
    # -----------------------------------------------------------------------
    @staticmethod
    def fetch_by_status(status: int, platform: str, limit: int = 100) -> List[ProcurementNoticeDto]:
        """按爬取状态查询公告记录."""
        with db() as session:
            result = session.execute(
                select(ProcurementNotice)
                .where(ProcurementNotice.status == status, ProcurementNotice.platform == platform)
                .order_by(ProcurementNotice.id.asc())
                .limit(limit)
            )
            return [orm_to_dto(row, ProcurementNoticeDto) for row in result.scalars().all()]

    # -----------------------------------------------------------------------
    # 更新 HTML
    # -----------------------------------------------------------------------
    @staticmethod
    def update_html(notice_id: int, html: str) -> bool:
        """更新详情页 HTML 内容，并将状态推进到 20."""
        with db.begin() as session:
            notice = session.get(ProcurementNotice, notice_id)
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
    def update_parsed(dto: ProcurementNoticeDto) -> bool:
        """更新 LLM 解析后的详情字段，并将状态推进到 30.

        Args:
            dto: 已填充解析结果的 ProcurementNoticeDto 实例（必须包含 id）

        Returns:
            是否更新成功
        """
        if not dto.id:
            logger.error("[ProcurementNoticeDao] update_parsed 失败: dto.id 为空")
            return False

        with db.begin() as session:
            existing = session.get(ProcurementNotice, dto.id)
            if not existing:
                logger.error(f"[ProcurementNoticeDao] update_parsed 失败: id={dto.id} 不存在")
                return False

            for key, value in dto.model_dump(exclude={"id", "created_at"}).items():
                setattr(existing, key, value)

            existing.status = 30
            existing.updated_at = datetime.now()
            return True
