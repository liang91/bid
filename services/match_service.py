"""招标信息匹配引擎.

三层匹配架构：
1. 粗筛（SQL硬规则）：时效性、地域、预算
2. 初筛第二阶段（语义排序）：Embedding 余弦相似度排序
3. 精筛（AI打分）：LLM 深度语义匹配，输出 Top3
"""
from loguru import logger
from models import NoticeDto
from dao import NoticeDao, SupplierDao
from providers import LLMEmbedding


class MatchService:
    """匹配引擎：封装粗筛 + 语义排序逻辑."""

    @staticmethod
    def rank_for_supplier(supplier_id: int, top_k: int = 200) -> list[tuple[float, NoticeDto]]:
        """为单个供应商执行匹配：粗筛 → 语义排序"""
        # -------------------------------------------------------------------
        # 第1层：SQL硬规则粗筛
        # -------------------------------------------------------------------
        supplier = SupplierDao.get(supplier_id)
        if not supplier:
            return []

        candidates = NoticeDao.fetch_candidates(
            region_names=supplier.service_regions,
            min_budget=float(supplier.min_budget) if supplier.min_budget else 0,
            max_budget=float(supplier.max_budget) if supplier.max_budget else 999999999.99,
        )
        if not candidates:
            logger.info(f"[MatchEngine] 供应商 {supplier.id} 硬规则粗筛后无候选")
            return []

        logger.info(f"[MatchEngine] 供应商 {supplier.id} 硬规则粗筛后: {len(candidates)} 条")

        # -------------------------------------------------------------------
        # 第2层：语义排序（Embedding 余弦相似度）
        # -------------------------------------------------------------------
        if not supplier.profile_embedding:
            return []

        # 收集有 embedding 的公告（supplier_profile_embedding 为 BLOB，需反序列化）
        candidate_with_vectors = []
        candidate_vectors = []
        for candidate in candidates:
            if not candidate.supplier_profile_embedding:
                continue
            candidate_with_vectors.append(candidate)
            candidate_vectors.append(candidate.supplier_profile_embedding)

        if not candidate_with_vectors:
            logger.warning(f"[MatchEngine] 供应商 {supplier.id} 候选公告均无 embedding，跳过语义排序")
            return []

        # 批量矩阵计算相似度
        scores = LLMEmbedding.similarities(supplier.profile_embedding, candidate_vectors)
        scored = list(zip(scores, candidate_with_vectors))
        scored.sort(key=lambda x: x[0], reverse=True)

        logger.info(
            f"[MatchEngine] 供应商 {supplier.id} 语义排序后取 Top{top_k}: "
            f"最高分 {scored[0][0]:.4f}, 最低分 {scored[min(top_k, len(scored)) - 1][0]:.4f}"
        )

        return scored[:top_k]
