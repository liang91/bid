"""notices 表的数据访问对象（SQLAlchemy 2.0）."""

from decimal import Decimal
from typing import List
from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert

from models import Notice, NoticeDto
from dao import db


class NoticeDao:
    """招标公告主表存储器."""

    @staticmethod
    def get(notice_id: int) -> NoticeDto | None:
        """根据公告ID查询."""
        with db() as session:
            obj = session.get(Notice, notice_id)
            if not obj:
                return None
            return NoticeDto.model_validate(obj)

    @staticmethod
    def create(notices: list[NoticeDto]) -> bool:
        """批量保存公告，自动去重（基于 URL）并更新已存在记录"""
        if not notices:
            return True
        datas = [notice.model_dump(exclude={"id", "created_at", "updated_at"}) for notice in notices]
        with db.begin() as session:
            stmt = insert(Notice).values(datas)
            session.execute(stmt)

        return True

    @staticmethod
    def get_latest(platform: str, part: str) -> NoticeDto | None:
        with db() as session:
            stmt = select(Notice).where(Notice.platform == platform, Notice.part == part).order_by(
                Notice.id.desc()).limit(1)
            row = session.execute(stmt).scalar()
            if row:
                return NoticeDto.model_validate(row)
            return None

    # -----------------------------------------------------------------------
    @staticmethod
    def fetch_candidates(
            region_names: list[str],
            min_budget: Decimal,
            max_budget: Decimal,
            limit: int = 25,
    ) -> list[NoticeDto]:
        """硬规则粗筛：根据地域、预算、采购方式、排除项、CA/中小企业、时效性筛选公告."""
        stmt = select(Notice).where(
            Notice.status == 30,
            Notice.bid_deadline > func.now(),
            Notice.budget >= min_budget,
            Notice.budget <= max_budget,
        )
        if region_names:
            stmt = stmt.where(Notice.region_province.in_(region_names))
        stmt = stmt.order_by(Notice.notice_date.desc()).limit(limit)

        with db() as session:
            result = session.execute(stmt)
            return [NoticeDto.model_validate(row) for row in result.scalars().all()]

    # -----------------------------------------------------------------------
    # 按状态查询
    # -----------------------------------------------------------------------
    @staticmethod
    def fetch_by_status(status: int, platform: str, part: str, limit: int = 100) -> List[NoticeDto]:
        """按爬取状态查询公告记录."""
        with db() as session:
            result = session.execute(
                select(Notice)
                .where(Notice.status == status, Notice.platform == platform, Notice.part == part)
                .order_by(Notice.id.asc())
                .limit(limit)
            )
            return [NoticeDto.model_validate(row) for row in result.scalars().all()]

    @staticmethod
    def fetch_unparsed(limit: int = 100) -> list[NoticeDto]:
        with db() as session:
            stmt = select(Notice).where(Notice.status == 20, Notice.html != '').order_by(Notice.id.asc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [NoticeDto.model_validate(row) for row in rows]

    # -----------------------------------------------------------------------
    # 更新 HTML
    # -----------------------------------------------------------------------
    @staticmethod
    def update_html(notice_id: int, html: str) -> bool:
        """保存html文件路径，并将状态推进到 20."""
        with db.begin() as session:
            stmt = update(Notice).where(Notice.id == notice_id).values(html=html, status=20)
            res = session.execute(stmt)
            return res.rowcount == 1

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
            dto.status = 30
            stmt = update(Notice).where(Notice.id == dto.id).values(dto.model_dump(exclude={"id", "created_at"}))
            res = session.execute(stmt)
            return res.rowcount == 1
