"""procurement_notices 表的数据访问对象."""

import json
import logging
from datetime import datetime
from typing import List, Optional

from model import ProcurementNotice

from .base import (
    BaseStorage,
    _parse_crawled_at,
    _to_datetime,
    parse_amount,
    parse_chinese_datetime,
)

logger = logging.getLogger(__name__)


class ProcurementNoticeDao(BaseStorage):
    """招标公告主表存储器."""

    def __init__(self, conn_params: dict):
        super().__init__(conn_params)
        self._insert_sql = self._build_insert_sql()

    def _build_insert_sql(self) -> str:
        """构建 INSERT ... ON DUPLICATE KEY UPDATE 语句."""
        fields = [
            "platform", "part", "title", "notice_type", "url",
            "region_province", "region_city", "region_district",
            "project_name", "project_no", "purchase_plan_no",
            "budget", "max_limit", "currency",
            "category_code", "category_name",
            "method", "joint_bid_allowed", "joint_bid_max_members", "sme_oriented",
            "notice_date", "doc_obtain_start", "doc_obtain_end",
            "bid_deadline", "bid_open_time",
            "bid_platform", "bid_platform_url", "ca_required", "doc_price",
            "purchaser_name", "purchaser_address", "purchaser_contact_person",
            "purchaser_contact_phone", "purchaser_region",
            "agency_name", "agency_address", "agency_contact_person",
            "agency_contact_phone", "agency_region",
            "project_contact_person", "project_contact_phone",
            "qualification_summary", "industry_tags", "keywords",
            "suggested_company_types", "geographic_advantage",
            "abstract", "html", "parse_time",
            "category_embedding",
            "status", "created_at", "updated_at",
        ]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        updates = ", ".join([f"{self._quote_field(f)}=VALUES({self._quote_field(f)})" for f in fields if f not in ("created_at",)])
        return (
            f"INSERT INTO procurement_notices ({columns}) VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )

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

        with self._get_cursor() as cursor:
            for batch in batches:
                params = [self._to_dict(n) for n in batch]
                try:
                    cursor.executemany(self._insert_sql, params)
                    urls = [p["url"] for p in params]
                    existing_urls = self._find_existing(cursor, urls)
                    updated += len(existing_urls)
                    inserted += len(params) - len(existing_urls)
                except Exception as e:
                    logger.error(f"[ProcurementNoticeDao] 批量写入失败: {e}")
                    failed += len(batch)

        return {"inserted": inserted, "updated": updated, "failed": failed, "skipped": skipped}

    def _find_existing(self, cursor, urls: List[str]) -> set:
        """查询给定的 URL 中哪些已经存在."""
        if not urls:
            return set()
        existing = set()
        batch_size = 500
        for i in range(0, len(urls), batch_size):
            batch = urls[i: i + batch_size]
            placeholders = ", ".join(["%s"] * len(batch))
            cursor.execute(
                f"SELECT url FROM procurement_notices WHERE url IN ({placeholders})",
                tuple(batch),
            )
            for row in cursor.fetchall():
                existing.add(row["url"])
        return existing

    def update_embedding(self, notice_id: int, embedding: list) -> bool:
        """更新公告的 Embedding 向量."""
        sql = "UPDATE procurement_notices SET category_embedding = %s WHERE id = %s"
        with self._get_cursor() as cursor:
            cursor.execute(sql, (json.dumps(embedding), notice_id))
            return cursor.rowcount > 0

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

        Args:
            region_names: 供应商服务的省份列表
            min_budget: 供应商最低预算偏好
            max_budget: 供应商最高预算偏好
            preferred_methods: 供应商偏好的采购方式列表
            excluded_keywords: 供应商排除的关键词列表
            sme_status: 供应商是否中小企业
            ca_ready: 供应商是否已有CA
            limit: 最大返回条数

        Returns:
            ProcurementNotice 列表（未解析 category_embedding）
        """
        if not region_names:
            return []

        conditions = [
            "status = 30",  # 已解析的公告
            "bid_deadline > NOW()",  # 未过期
            "region_province IN (%s)" % ", ".join(["%s"] * len(region_names)),
            "budget >= %s",
            "budget <= %s",
        ]
        params = list(region_names) + [min_budget, max_budget]

        # 采购方式过滤
        if preferred_methods:
            conditions.append("method IN (%s)" % ", ".join(["%s"] * len(preferred_methods)))
            params.extend(preferred_methods)

        # 排除关键词（标题/项目名称/摘要中不能出现）
        for kw in excluded_keywords:
            if kw.strip():
                conditions.append("(title NOT LIKE %s AND project_name NOT LIKE %s AND abstract NOT LIKE %s)")
                like_param = f"%%{kw.strip()}%%"
                params.extend([like_param, like_param, like_param])

        # 公告要求中小企业，供应商必须满足
        conditions.append("(sme_oriented = 0 OR %s = 1)")
        params.append(sme_status)

        # 公告要求CA，供应商必须满足
        conditions.append("(ca_required = 0 OR %s = 1)")
        params.append(ca_ready)

        sql = (
            "SELECT * FROM procurement_notices WHERE "
            + " AND ".join(conditions)
            + " ORDER BY notice_date DESC LIMIT %s"
        )
        params.append(limit)

        with self._get_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        return [self._from_row(row) for row in rows]

    def exists(self, url: str) -> bool:
        """检查 URL 是否已存在."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM procurement_notices WHERE url = %s LIMIT 1", (url,))
            return cursor.fetchone() is not None

    def dedup_by_url(self, notices: List[ProcurementNotice]) -> List[ProcurementNotice]:
        """基于数据库已有 URL 去重，返回尚未入库的公告."""
        if not notices:
            return []

        urls = [n.url for n in notices if n.url]
        if not urls:
            return notices

        with self._get_cursor() as cursor:
            existing = self._find_existing(cursor, urls)

        return [n for n in notices if n.url not in existing]

    def insert_list(self, notices: List[ProcurementNotice], batch_size: int = 100) -> dict:
        """仅插入列表页获取到的公告（INSERT IGNORE，不更新已有记录）.

        适用于 fetch_list 阶段，状态默认为 1（获取概要信息）。

        Returns:
            {"inserted": int, "skipped": int}
        """
        if not notices:
            return {"inserted": 0, "skipped": 0}

        fields = [
            "platform", "part", "title", "notice_type", "url", "region_province",
            "method", "notice_date", "purchaser_name", "status", "created_at", "updated_at",
        ]
        columns = ", ".join([self._quote_field(f) for f in fields])
        placeholders = ", ".join([f"%({f})s" for f in fields])
        sql = f"INSERT IGNORE INTO procurement_notices ({columns}) VALUES ({placeholders})"

        inserted = 0
        batches = [notices[i: i + batch_size] for i in range(0, len(notices), batch_size)]
        with self._get_cursor() as cursor:
            for batch in batches:
                params = [self._to_dict(n) for n in batch]
                try:
                    cursor.executemany(sql, params)
                    inserted += cursor.rowcount
                except Exception as e:
                    logger.error(f"[ProcurementNoticeDao] 列表页批量插入失败: {e}")

        skipped = len(notices) - inserted
        return {"inserted": inserted, "skipped": skipped}

    def fetch_by_status(self, status: int, platform: str, limit: int = 100) -> List[ProcurementNotice]:
        """按爬取状态查询公告记录.

        Args:
            status: 1=获取概要信息, 20=获取了网页内容, 30=解析出了公告内容
            platform: 平台名称
            limit: 最大返回条数

        Returns:
            ProcurementNotice 列表
        """
        sql = """
            SELECT * FROM procurement_notices
            WHERE status = %s AND platform = %s
            ORDER BY id ASC
            LIMIT %s
        """
        params = (status, platform, limit)

        with self._get_cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [self._from_row(row) for row in rows]

    def update_html(self, notice_id: int, html: str) -> bool:
        """更新详情页 HTML 内容，并将状态推进到 20.

        Returns:
            是否更新成功
        """
        sql = """
            UPDATE procurement_notices
            SET html = %s, status = 20, updated_at = NOW()
            WHERE id = %s
        """
        with self._get_cursor() as cursor:
            cursor.execute(sql, (html, notice_id))
            return cursor.rowcount > 0

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

        update_fields = [
            "region_province", "region_city", "region_district",
            "project_name", "project_no", "purchase_plan_no",
            "budget", "max_limit", "currency",
            "category_code", "category_name",
            "method", "joint_bid_allowed", "joint_bid_max_members", "sme_oriented",
            "notice_date", "doc_obtain_start", "doc_obtain_end",
            "bid_deadline", "bid_open_time",
            "bid_platform", "bid_platform_url", "ca_required", "doc_price",
            "purchaser_name", "purchaser_address", "purchaser_contact_person",
            "purchaser_contact_phone", "purchaser_region",
            "agency_name", "agency_address", "agency_contact_person",
            "agency_contact_phone", "agency_region",
            "project_contact_person", "project_contact_phone",
            "qualification_summary", "industry_tags", "keywords",
            "suggested_company_types", "geographic_advantage",
            "abstract", "parse_time",
            "category_embedding",
            "status", "updated_at",
        ]

        d = self._to_dict(notice)
        set_clause = ", ".join([f"{self._quote_field(f)} = %({f})s" for f in update_fields])
        sql = f"UPDATE procurement_notices SET {set_clause} WHERE id = %(id)s"

        params = {f: d[f] for f in update_fields}
        params["id"] = notice.id

        with self._get_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount > 0

    @staticmethod
    def _from_row(row: dict) -> ProcurementNotice:
        """将数据库查询结果行转换为 ProcurementNotice 实例."""
        notice = ProcurementNotice()

        for key, val in row.items():
            if not hasattr(notice, key):
                continue
            if val is None:
                continue

            if key in ("industry_tags", "keywords", "suggested_company_types", "category_embedding"):
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        val = []
                elif not isinstance(val, list):
                    val = []

            if key in ("id", "status", "joint_bid_allowed", "joint_bid_max_members",
                       "sme_oriented", "ca_required"):
                val = int(val) if val is not None else 0

            setattr(notice, key, val)

        if row.get("html"):
            notice.html = row["html"]

        return notice

    @staticmethod
    def _to_dict(notice: ProcurementNotice) -> dict:
        """将 ProcurementNotice 转换为可插入 procurement_notices 的字典."""
        d = notice.to_dict()

        def _to_json(val):
            if val and isinstance(val, list) and len(val) > 0:
                return json.dumps(val, ensure_ascii=False)
            return None

        from .base import _to_decimal

        return {
            "platform": d.get("platform") or "中国政府采购网",
            "part": d.get("part") or "",
            "title": d.get("title") or d.get("project_name") or "",
            "notice_type": d.get("notice_type") or "",
            "url": d.get("url") or "",

            "region_province": d.get("region_province") or "",
            "region_city": d.get("region_city") or "",
            "region_district": d.get("region_district") or "",

            "project_name": d.get("project_name") or d.get("title") or "",
            "project_no": d.get("project_no") or "",
            "purchase_plan_no": d.get("purchase_plan_no") or "",

            "budget": _to_decimal(parse_amount(d.get("budget"))),
            "max_limit": _to_decimal(parse_amount(d.get("max_limit"))),
            "currency": d.get("currency") or "CNY",

            "category_code": d.get("category_code") or "",
            "category_name": d.get("category_name") or "",

            "method": d.get("method") or d.get("notice_type") or "",
            "joint_bid_allowed": d.get("joint_bid_allowed") or 0,
            "joint_bid_max_members": d.get("joint_bid_max_members") or 1,
            "sme_oriented": d.get("sme_oriented") or 0,

            "notice_date": _to_datetime(parse_chinese_datetime(d.get("notice_date"))),
            "doc_obtain_start": _to_datetime(parse_chinese_datetime(d.get("doc_obtain_start"))),
            "doc_obtain_end": _to_datetime(parse_chinese_datetime(d.get("doc_obtain_end"))),
            "bid_deadline": _to_datetime(parse_chinese_datetime(d.get("bid_deadline"))),
            "bid_open_time": _to_datetime(parse_chinese_datetime(d.get("bid_open_time"))),

            "bid_platform": d.get("bid_platform") or "",
            "bid_platform_url": d.get("bid_platform_url") or "",
            "ca_required": d.get("ca_required") or 0,
            "doc_price": _to_decimal(parse_amount(d.get("doc_price"))),

            "purchaser_name": d.get("purchaser_name") or d.get("purchaser") or "",
            "purchaser_address": d.get("purchaser_address") or "",
            "purchaser_contact_person": d.get("purchaser_contact_person") or "",
            "purchaser_contact_phone": d.get("purchaser_contact_phone") or "",
            "purchaser_region": d.get("purchaser_region") or d.get("region") or "",

            "agency_name": d.get("agency_name") or "",
            "agency_address": d.get("agency_address") or "",
            "agency_contact_person": d.get("agency_contact_person") or "",
            "agency_contact_phone": d.get("agency_contact_phone") or "",
            "agency_region": d.get("agency_region") or "",

            "project_contact_person": d.get("project_contact_person") or "",
            "project_contact_phone": d.get("project_contact_phone") or "",

            "qualification_summary": d.get("qualification_summary") or None,
            "industry_tags": _to_json(d.get("industry_tags")),
            "keywords": _to_json(d.get("keywords")),
            "suggested_company_types": _to_json(d.get("suggested_company_types")),
            "geographic_advantage": d.get("geographic_advantage") or "",

            "abstract": d.get("abstract") or "",
            "html": d.get("html") or "",
            "parse_time": datetime.now(),
            "category_embedding": _to_json(d.get("category_embedding")),

            "status": d.get("status") or 1,
            "created_at": _parse_crawled_at(d.get("created_at")),
            "updated_at": datetime.now(),
        }
