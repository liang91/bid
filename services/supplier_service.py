from loguru import logger

from dao import SupplierDao, NoticeDao, MatchDao
from models import MatchNoticeScore, MatchDto
from providers import LLMEmbedding


class SupplierService:
    @staticmethod
    def filtered_notices(supplier_id: int, top_k: int = 200):
        """
        招标信息推荐，三层匹配架构，本函数执行前两步
            1. 粗筛（SQL硬规则）：时效性、地域、预算
            2. 初筛第二阶段（语义排序）：Embedding 余弦相似度排序
            3. 精筛（AI打分）：LLM 深度语义匹配，输出 Top3
        """
        # -------------------------------------------------------------------
        # 第1层：SQL硬规则粗筛
        # -------------------------------------------------------------------
        supplier = SupplierDao.get(supplier_id)
        if not supplier:
            return

        candidates = NoticeDao.fetch_candidates(
            region_names=supplier.service_regions,
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget,
        )
        if not candidates:
            logger.info(f"[filtered_notices] 供应商 {supplier.id} 硬规则粗筛后无候选")
            return

        logger.info(f"[filtered_notices] 供应商 {supplier.id} 硬规则粗筛后: {len(candidates)} 条")

        # -------------------------------------------------------------------
        # 第2层：语义排序（Embedding 余弦相似度）
        # -------------------------------------------------------------------
        if not supplier.profile_embedding:
            return

        # 收集有 embedding 的公告（supplier_profile_embedding 为 BLOB，需反序列化）
        candidate_with_vectors = []
        candidate_vectors = []
        for candidate in candidates:
            if not candidate.supplier_profile_embedding:
                continue
            candidate_with_vectors.append(candidate)
            candidate_vectors.append(candidate.supplier_profile_embedding)

        if not candidate_with_vectors:
            logger.warning(f"[filtered_notices] 供应商 {supplier.id} 候选公告均无 embedding，跳过语义排序")
            return

        # 批量矩阵计算相似度
        scores = LLMEmbedding.similarities(supplier.profile_embedding, candidate_vectors)
        scored = list(zip(scores, candidate_with_vectors))
        scored.sort(key=lambda x: x[0], reverse=True)

        filtered_notices = [MatchNoticeScore(score=score, notice_id=notice.id) for score, notice in scored[:top_k]]
        match_id = MatchDao.create(MatchDto(supplier_id=supplier_id, filtered_notices=filtered_notices))
        logger.info(f"[filtered_notices] 供应商 {supplier_id} 完成粗筛，结果ID: {match_id}")


    @staticmethod
    def set_profile_embeddings():
        suppliers = SupplierDao.unembed()
        for supplier in suppliers:
            SupplierService.update_profile_embedding(supplier.id)

    @staticmethod
    def update_profile_embedding(supplier_id: int) -> bool:
        supplier = SupplierDao.get(supplier_id)
        if not supplier:
            return False
        profile = f"公司业务范围：{supplier.business_scope}。具备的资质：{supplier.qualification_summary}"
        vector = LLMEmbedding.embed(profile, text_type='query')
        return SupplierDao.update_embedding(supplier.id, vector)
