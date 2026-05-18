"""招标信息匹配引擎.

三层匹配架构：
1. 粗筛（SQL硬规则）：地域、预算、采购方式、排除项、CA/中小企业、时效性
2. 初筛第二阶段（语义排序）：Embedding 余弦相似度排序
3. 精筛（AI打分）：LLM 深度语义匹配，输出 Top3

使用方式：
    from match.match_engine import MatchEngine
    engine = MatchEngine()
    ranked = engine.rank_for_supplier(supplier_id, top_k=200)
"""
import logging
from typing import List, Tuple

from model import ProcurementNotice, SupplierProfile
from dao import (
    ProcurementNoticeDao,
    SupplierProfileDao,
    SupplierServiceRegionDao,
)
from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class MatchEngine:
    """匹配引擎：封装粗筛 + 语义排序逻辑."""

    def __init__(self):
        self.notice_dao = ProcurementNoticeDao.instance()
        self.supplier_dao = SupplierProfileDao.instance()
        self.region_dao = SupplierServiceRegionDao.instance()

    def rank_for_supplier(
        self,
        supplier: SupplierProfile,
        top_k: int = 200,
    ) -> List[Tuple[float, ProcurementNotice]]:
        """为单个供应商执行匹配：粗筛 → 语义排序.

        Args:
            supplier: 供应商画像
            top_k: 语义排序后保留的 Top K 条

        Returns:
            [(similarity_score, notice), ...]，按相似度降序排列
        """
        # -------------------------------------------------------------------
        # 第1层：SQL硬规则粗筛
        # -------------------------------------------------------------------
        service_regions = self.region_dao.get_regions_by_supplier(supplier.id)
        if not service_regions:
            logger.warning(f"[MatchEngine] 供应商 {supplier.id} 未配置服务地区，跳过匹配")
            return []

        preferred_methods = [
            m.strip() for m in supplier.preferred_methods.split(",") if m.strip()
        ]
        excluded_keywords = [
            k.strip() for k in supplier.excluded_keywords.split(",") if k.strip()
        ]

        candidates = self.notice_dao.fetch_candidates_for_matching(
            region_names=service_regions,
            min_budget=float(supplier.min_budget) if supplier.min_budget else 0,
            max_budget=float(supplier.max_budget) if supplier.max_budget else 999999999.99,
            preferred_methods=preferred_methods,
            excluded_keywords=excluded_keywords,
            sme_status=supplier.sme_status,
            ca_ready=supplier.ca_ready,
            limit=5000,
        )

        if not candidates:
            logger.info(f"[MatchEngine] 供应商 {supplier.id} 硬规则粗筛后无候选")
            return []

        logger.info(
            f"[MatchEngine] 供应商 {supplier.id} 硬规则粗筛后: {len(candidates)} 条"
        )

        # -------------------------------------------------------------------
        # 第2层：语义排序（Embedding 余弦相似度）
        # -------------------------------------------------------------------
        supplier_vec = supplier.business_embedding
        if not supplier_vec:
            # 如果供应商没有预计算 embedding，实时计算并缓存
            supplier_vec = EmbeddingService.get_supplier_embedding(supplier)
            if supplier_vec:
                self.supplier_dao.update_embedding(supplier.id, supplier_vec)

        if not supplier_vec:
            logger.warning(
                f"[MatchEngine] 供应商 {supplier.id} embedding 计算失败，跳过语义排序"
            )
            return []

        # 收集有 embedding 的公告
        notices_with_vec = []
        notice_vecs = []
        for notice in candidates:
            if notice.category_embedding:
                notices_with_vec.append(notice)
                notice_vecs.append(notice.category_embedding)

        if not notices_with_vec:
            logger.warning(
                f"[MatchEngine] 供应商 {supplier.id} 候选公告均无 embedding，跳过语义排序"
            )
            return []

        # 批量矩阵计算相似度
        scores = EmbeddingService.similarity_matrix(supplier_vec, notice_vecs)
        scored = list(zip(scores, notices_with_vec))
        scored.sort(key=lambda x: x[0], reverse=True)

        logger.info(
            f"[MatchEngine] 供应商 {supplier.id} 语义排序后取 Top{top_k}: "
            f"最高分 {scored[0][0]:.4f}, 最低分 {scored[min(top_k, len(scored)) - 1][0]:.4f}"
        )

        return scored[:top_k]

    def batch_rank_for_all_suppliers(
        self,
        top_k: int = 200,
    ) -> dict:
        """为所有供应商执行匹配.

        Returns:
            {supplier_id: [(score, notice), ...]}
        """
        suppliers = self.supplier_dao.list_all()
        results = {}
        for supplier in suppliers:
            try:
                results[supplier.id] = self.rank_for_supplier(supplier, top_k=top_k)
            except Exception as e:
                logger.error(f"[MatchEngine] 供应商 {supplier.id} 匹配失败: {e}")
                results[supplier.id] = []
        return results
