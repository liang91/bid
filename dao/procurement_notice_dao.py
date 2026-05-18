"""procurement_notices 表的数据访问对象（SQLAlchemy 2.0）."""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert

from model import ProcurementNotice

from .base import (
    session_scope,
    _parse_crawled_at,
    _to_decimal,
    parse_amount,
    parse_chinese_datetime,
    _DEFAULT_DATETIME,
)

logger = logging.getLogger(__name__)


class ProcurementNoticeDao:
    """招标公告主表存储器."""

    # -----------------------------------------------------------------------
    # 内部辅助：将 ProcurementNotice 转为 INSERT 用的字典
    # -----------------------------------------------------------------------
    @staticmethod
    def _notice_to_values(notice: ProcurementNotice) -> dict:
        """将 ProcurementNotice 转换为可插入/更新的字典（含类型转换）."""
        return {
            "platform": notice.platform or "中国政府采购网",
            "part": notice.part or "",
            "title": notice.title or notice.project_name or "",
            "notice_type": notice.notice_type or "",
            "url": notice.url or "",
            "region_province": notice.region_province or "",
            "region_city": notice.region_city or "",
            "region_district": notice.region_district or "",
            "project_name": notice.project_name or notice.title or "",
            "project_no": notice.project_no or "",
            "purchase_plan_no": notice.purchase_plan_no or "",
            "budget": parse_amount(notice.budget) or _to_decimal(notice.budget),
            "max_limit": parse_amount(notice.max_limit) or _to_decimal(notice.max_limit),
            "currency": notice.currency or "CNY",
            "category_code": notice.category_code or "",
            "category_name": notice.category_name or "",
            "method": notice.method or notice.notice_type or "",
            "joint_bid_allowed": notice.joint_bid_allowed or 0,
            "joint_bid_max_members": notice.joint_bid_max_members or 1,
            "sme_oriented": notice.sme_oriented or 0,
            "notice_date": parse_chinese_datetime(notice.notice_date) or _DEFAULT_DATETIME,
            "doc_obtain_start": parse_chinese_datetime(notice.doc_obtain_start) or _DEFAULT_DATETIME,
            "doc_obtain_end": parse_chinese_datetime(notice.doc_obtain_end) or _DEFAULT_DATETIME,
            "bid_deadline": parse_chinese_datetime(notice.bid_deadline) or _DEFAULT_DATETIME,
            "bid_open_time": parse_chinese_datetime(notice.bid_open_time) or _DEFAULT_DATETIME,
            "bid_platform": notice.bid_platform or "",
            "bid_platform_url": notice.bid_platform_url or "",
            "ca_required": notice.ca_required or 0,
            "doc_price": parse_amount(notice.doc_price) or _to_decimal(notice.doc_price),
            "purchaser_name": notice.purchaser_name or getattr(notice, "purchaser", "") or "",
            "purchaser_address": notice.purchaser_address or "",
            "purchaser_contact_person": notice.purchaser_contact_person or "",
            "purchaser_contact_phone": notice.purchaser_contact_phone or "",
            "purchaser_region": notice.purchaser_region or getattr(notice, "region", "") or "",
            "agency_name": notice.agency_name or "",
            "agency_address": notice.agency_address or "",
            "agency_contact_person": notice.agency_contact_person or "",
            "agency_contact_phone": notice.agency_contact_phone or "",
            "agency_region": notice.agency_region or "",
            "project_contact_person": notice.project_contact_person or "",
            "project_contact_phone": notice.project_contact_phone or "",
            "qualification_summary": notice.qualification_summary or None,
            "industry_tags": notice.industry_tags if notice.industry_tags else None,
            "keywords": notice.keywords if notice.keywords else None,
            "suggested_company_types": notice.suggested_company_types if notice.suggested_company_types else None,
            "geographic_advantage": notice.geographic_advantage or "",
            "abstract": notice.abstract or "",
            "html": notice.html or "",
            "parse_time": datetime.now(),
            "category_embedding": notice.category_embedding if notice.category_embedding else None,
            "status": notice.status or 1,
            "created_at": _parse_crawled_at(notice.created_at),
            "updated_at": datetime.now(),
        }

    @staticmethod
    def _is_open_tender(notice: ProcurementNotice) -> bool:
        """判断公告是否为公开招标类型（入库前严格校验）."""
        if not notice.notice_type:
            return False
        nt = notice.notice_type.strip()
        if "公开招标" not in nt:
            return False
        exclude_keywords = ("中标", "成交", "结果", "更正", "废标", "终止")
        if any(kw in nt for kw in exclude_keywords):
            return False
        return True

    # -----------------------------------------------------------------------
    # 批量保存（INSERT ... ON DUPLICATE KEY UPDATE）
    # -----------------------------------------------------------------------
    def save(self, notices: List[ProcurementNotice], batch_size: int = 100) -> dict:
        """批量保存公告，自动去重（基于 URL）并更新已存在记录.

        仅保存 notice_type 包含"公开招标"的公告，其他类型自动过滤。

        Returns:
            {"inserted": int, "updated": int, "failed": int, "skipped": int}
        """
        if not notices:
            return {"inserted": 0, "updated": 0, "failed": 0, "skipped": 0}

        original_count = len(notices)
        notices = [n for n in notices if self._is_open_tender(n)]
        skipped = original_count - len(notices)
        if skipped > 0:
            logger.info(f"[ProcurementNoticeDao] 过滤非公开招标 {skipped} 条，实际入库 {len(notices)} 条")

        inserted = updated = failed = 0
        batches = [notices[i: i + batch_size] for i in range(0, len(notices), batch_size)]

        with session_scope() as session:
            for batch in batches:
                values = [self._notice_to_values(n) for n in batch]
                try:
                    stmt = insert(ProcurementNotice).values(values)
                    # ON DUPLICATE KEY UPDATE 除 id/created_at 外全部更新
                    update_dict = {
                        c.name: getattr(stmt.inserted, c.name)
                        for c in ProcurementNotice.__table__.columns
                        if c.name not in ("id", "created_at")
                    }
                    stmt = stmt.on_duplicate_key_update(**update_dict)
                    session.execute(stmt)
                    session.commit()

                    # 统计：查询本批 URL 中已存在的数量作为 updated
                    urls = [n.url for n in batch if n.url]
                    if urls:
                        existing = session.execute(
                            select(ProcurementNotice.url).where(
                                ProcurementNotice.url.in_(urls)
                            )
                        ).scalars().all()
                        updated += len(existing)
                        inserted += len(batch) - len(existing)
                    else:
                        inserted += len(batch)
                except Exception as e:
                    session.rollback()
                    logger.error(f"[ProcurementNoticeDao] 批量写入失败: {e}")
                    failed += len(batch)

        return {"inserted": inserted, "updated": updated, "failed": failed, "skipped": skipped}

    # -----------------------------------------------------------------------
    # Embedding 更新
    # -----------------------------------------------------------------------
    def update_embedding(self, notice_id: int, embedding: list) -> bool:
        """更新公告的 Embedding 向量."""
        with session_scope() as session:
            notice = session.get(ProcurementNotice, notice_id)
            if not notice:
                return False
            notice.category_embedding = embedding
            session.commit()
            return True

    # -----------------------------------------------------------------------
    # 粗筛查询（硬规则）
    # -----------------------------------------------------------------------
    def fetch_candidates_for_matching(
        self,
        region_names: list,
        min_budget: float,
        max_budget: float,
        preferred_methods: list,
        excluded_keywords: list,
        sme_status: int,
        ca_ready: int,
        limit: int = 2000,
    ) -> list:
        """硬规则粗筛：根据地域、预算、采购方式、排除项、CA/中小企业、时效性筛选公告.

        Returns:
            ProcurementNotice 列表
        """
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

        with session_scope() as session:
            result = session.execute(stmt)
            return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # URL 存在性检查
    # -----------------------------------------------------------------------
    def exists(self, url: str) -> bool:
        """检查 URL 是否已存在."""
        with session_scope() as session:
            result = session.execute(
                select(ProcurementNotice.id).where(ProcurementNotice.url == url).limit(1)
            )
            return result.scalar() is not None

    # -----------------------------------------------------------------------
    # URL 去重
    # -----------------------------------------------------------------------
    def dedup_by_url(self, notices: List[ProcurementNotice]) -> List[ProcurementNotice]:
        """基于数据库已有 URL 去重，返回尚未入库的公告."""
        if not notices:
            return []

        urls = [n.url for n in notices if n.url]
        if not urls:
            return notices

        with session_scope() as session:
            existing = session.execute(
                select(ProcurementNotice.url).where(ProcurementNotice.url.in_(urls))
            ).scalars().all()
            existing_set = set(existing)

        return [n for n in notices if n.url not in existing_set]

    # -----------------------------------------------------------------------
    # 列表页批量插入（INSERT IGNORE）
    # -----------------------------------------------------------------------
    def insert_list(self, notices: List[ProcurementNotice], batch_size: int = 100) -> dict:
        """仅插入列表页获取到的公告（INSERT IGNORE，不更新已有记录）.

        Returns:
            {"inserted": int, "skipped": int}
        """
        if not notices:
            return {"inserted": 0, "skipped": 0}

        inserted = 0
        batches = [notices[i: i + batch_size] for i in range(0, len(notices), batch_size)]

        with session_scope() as session:
            for batch in batches:
                values = []
                for n in batch:
                    values.append({
                        "platform": n.platform or "中国政府采购网",
                        "part": n.part or "",
                        "title": n.title or n.project_name or "",
                        "notice_type": n.notice_type or "",
                        "url": n.url or "",
                        "region_province": n.region_province or "",
                        "method": n.method or n.notice_type or "",
                        "notice_date": parse_chinese_datetime(n.notice_date) or _DEFAULT_DATETIME,
                        "purchaser_name": n.purchaser_name or getattr(n, "purchaser", "") or "",
                        "status": 1,
                        "created_at": _parse_crawled_at(n.created_at),
                        "updated_at": datetime.now(),
                    })
                try:
                    stmt = insert(ProcurementNotice).values(values).prefix_with("IGNORE")
                    result = session.execute(stmt)
                    session.commit()
                    inserted += result.rowcount
                except Exception as e:
                    session.rollback()
                    logger.error(f"[ProcurementNoticeDao] 列表页批量插入失败: {e}")

        skipped = len(notices) - inserted
        return {"inserted": inserted, "skipped": skipped}

    # -----------------------------------------------------------------------
    # 按状态查询
    # -----------------------------------------------------------------------
    def fetch_by_status(self, status: int, platform: str, limit: int = 100) -> List[ProcurementNotice]:
        """按爬取状态查询公告记录."""
        with session_scope() as session:
            result = session.execute(
                select(ProcurementNotice)
                .where(ProcurementNotice.status == status, ProcurementNotice.platform == platform)
                .order_by(ProcurementNotice.id.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # 更新 HTML
    # -----------------------------------------------------------------------
    def update_html(self, notice_id: int, html: str) -> bool:
        """更新详情页 HTML 内容，并将状态推进到 20."""
        with session_scope() as session:
            notice = session.get(ProcurementNotice, notice_id)
            if not notice:
                return False
            notice.html = html
            notice.status = 20
            notice.updated_at = datetime.now()
            session.commit()
            return True

    # -----------------------------------------------------------------------
    # 更新解析结果
    # -----------------------------------------------------------------------
    def update_parsed(self, notice: ProcurementNotice) -> bool:
        """更新 LLM 解析后的详情字段，并将状态推进到 30.

        Args:
            notice: 已填充解析结果的 ProcurementNotice 实例（必须包含 id）

        Returns:
            是否更新成功
        """
        if not notice.id:
            logger.error("[ProcurementNoticeDao] update_parsed 失败: notice.id 为空")
            return False

        with session_scope() as session:
            existing = session.get(ProcurementNotice, notice.id)
            if not existing:
                logger.error(f"[ProcurementNoticeDao] update_parsed 失败: id={notice.id} 不存在")
                return False

            # 金额转换
            existing.budget = parse_amount(notice.budget) or _to_decimal(notice.budget)
            existing.max_limit = parse_amount(notice.max_limit) or _to_decimal(notice.max_limit)
            existing.doc_price = parse_amount(notice.doc_price) or _to_decimal(notice.doc_price)

            # 时间转换
            existing.notice_date = parse_chinese_datetime(notice.notice_date) or _DEFAULT_DATETIME
            existing.doc_obtain_start = parse_chinese_datetime(notice.doc_obtain_start) or _DEFAULT_DATETIME
            existing.doc_obtain_end = parse_chinese_datetime(notice.doc_obtain_end) or _DEFAULT_DATETIME
            existing.bid_deadline = parse_chinese_datetime(notice.bid_deadline) or _DEFAULT_DATETIME
            existing.bid_open_time = parse_chinese_datetime(notice.bid_open_time) or _DEFAULT_DATETIME

            # 字符串字段（含回退逻辑）
            existing.platform = notice.platform or existing.platform or "中国政府采购网"
            existing.part = notice.part or existing.part or ""
            existing.title = notice.title or notice.project_name or existing.title or ""
            existing.notice_type = notice.notice_type or existing.notice_type or ""
            existing.url = notice.url or existing.url or ""
            existing.region_province = notice.region_province or existing.region_province or ""
            existing.region_city = notice.region_city or existing.region_city or ""
            existing.region_district = notice.region_district or existing.region_district or ""
            existing.project_name = notice.project_name or notice.title or existing.project_name or ""
            existing.project_no = notice.project_no or existing.project_no or ""
            existing.purchase_plan_no = notice.purchase_plan_no or existing.purchase_plan_no or ""
            existing.currency = notice.currency or existing.currency or "CNY"
            existing.category_code = notice.category_code or existing.category_code or ""
            existing.category_name = notice.category_name or existing.category_name or ""
            existing.method = notice.method or notice.notice_type or existing.method or ""
            existing.joint_bid_allowed = notice.joint_bid_allowed or existing.joint_bid_allowed or 0
            existing.joint_bid_max_members = notice.joint_bid_max_members or existing.joint_bid_max_members or 1
            existing.sme_oriented = notice.sme_oriented or existing.sme_oriented or 0
            existing.bid_platform = notice.bid_platform or existing.bid_platform or ""
            existing.bid_platform_url = notice.bid_platform_url or existing.bid_platform_url or ""
            existing.ca_required = notice.ca_required or existing.ca_required or 0
            existing.purchaser_name = notice.purchaser_name or getattr(notice, "purchaser", "") or existing.purchaser_name or ""
            existing.purchaser_address = notice.purchaser_address or existing.purchaser_address or ""
            existing.purchaser_contact_person = notice.purchaser_contact_person or existing.purchaser_contact_person or ""
            existing.purchaser_contact_phone = notice.purchaser_contact_phone or existing.purchaser_contact_phone or ""
            existing.purchaser_region = notice.purchaser_region or getattr(notice, "region", "") or existing.purchaser_region or ""
            existing.agency_name = notice.agency_name or existing.agency_name or ""
            existing.agency_address = notice.agency_address or existing.agency_address or ""
            existing.agency_contact_person = notice.agency_contact_person or existing.agency_contact_person or ""
            existing.agency_contact_phone = notice.agency_contact_phone or existing.agency_contact_phone or ""
            existing.agency_region = notice.agency_region or existing.agency_region or ""
            existing.project_contact_person = notice.project_contact_person or existing.project_contact_person or ""
            existing.project_contact_phone = notice.project_contact_phone or existing.project_contact_phone or ""
            existing.qualification_summary = notice.qualification_summary or existing.qualification_summary
            existing.geographic_advantage = notice.geographic_advantage or existing.geographic_advantage or ""
            existing.abstract = notice.abstract or existing.abstract or ""
            existing.parse_time = datetime.now()

            # JSON 字段
            if notice.industry_tags:
                existing.industry_tags = notice.industry_tags
            if notice.keywords:
                existing.keywords = notice.keywords
            if notice.suggested_company_types:
                existing.suggested_company_types = notice.suggested_company_types
            if notice.category_embedding:
                existing.category_embedding = notice.category_embedding

            existing.status = 30
            existing.updated_at = datetime.now()
            session.commit()
            return True
