"""招标信息匹配引擎.

三层匹配架构：
1. 粗筛（SQL硬规则）：地域、预算、采购方式、排除项、CA/中小企业、时效性
2. 初筛第二阶段（语义排序）：Embedding 余弦相似度排序
3. 精筛（AI打分）：LLM 深度语义匹配，输出 Top3
"""
from loguru import logger
from models import NoticeDto, Notice
from dao import NoticeDao, SupplierDao, db
import numpy as np
from sqlalchemy import select
from providers import LLMEmbedding


class MatchService:
    """匹配引擎：封装粗筛 + 语义排序逻辑."""

    @staticmethod
    def rank_for_supplier(supplier_id: int, top_k: int = 200) -> list[tuple[float, NoticeDto]]:
        """为单个供应商执行匹配：粗筛 → 语义排序"""
        # -------------------------------------------------------------------
        # 第1层：SQL硬规则粗筛
        # -------------------------------------------------------------------
        supplier = SupplierDao.get_by_id(supplier_id)
        if not supplier:
            return []

        candidates = NoticeDao.fetch_candidates_for_matching(
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
        supplier_vec = np.frombuffer(supplier.profile_embedding, dtype=np.float32).tolist()

        # 收集有 embedding 的公告（supplier_profile_embedding 为 BLOB，需反序列化）
        candidate_with_vectors = []
        candidate_vectors = []
        for candidate in candidates:
            if not candidate.supplier_profile_embedding:
                continue
            vec = np.frombuffer(candidate.supplier_profile_embedding, dtype=np.float32).tolist()
            candidate_with_vectors.append(candidate)
            candidate_vectors.append(vec)

        if not candidate_with_vectors:
            logger.warning(f"[MatchEngine] 供应商 {supplier.id} 候选公告均无 embedding，跳过语义排序")
            return []

        # 批量矩阵计算相似度
        scores = LLMEmbedding.similarity_matrix(supplier_vec, candidate_vectors)
        scored = list(zip(scores, candidate_with_vectors))
        scored.sort(key=lambda x: x[0], reverse=True)

        logger.info(
            f"[MatchEngine] 供应商 {supplier.id} 语义排序后取 Top{top_k}: "
            f"最高分 {scored[0][0]:.4f}, 最低分 {scored[min(top_k, len(scored)) - 1][0]:.4f}"
        )

        return scored[:top_k]

    # ---------------------------------------------------------------------------
    # 补算公告 Embedding
    # ---------------------------------------------------------------------------
    @staticmethod
    def run_backfill_notice(args):
        with db() as session:
            stmt = (
                select(Notice.id)
                .where(
                    Notice.status == 30,
                    Notice.supplier_profile.isnot(None),
                    Notice.supplier_profile != "",
                    Notice.supplier_profile_embedding.is_(None),
                )
                .order_by(Notice.id.desc())
            )
            if args.limit > 0:
                stmt = stmt.limit(args.limit)
            result = session.execute(stmt)
            notice_ids = [row[0] for row in result.all()]

        if not notice_ids:
            logger.info("没有待补算 supplier_profile_embedding 的公告")
            return

        logger.info(f"待补算公告共 {len(notice_ids)} 条")

        success = failed = skipped = 0
        for i in range(0, len(notice_ids), args.batch):
            batch_ids = notice_ids[i: i + args.batch]

            with db() as session:
                notices = session.execute(
                    select(Notice).where(Notice.id.in_(batch_ids))
                ).scalars().all()

            for notice in notices:
                if not notice.supplier_profile:
                    skipped += 1
                    continue
                try:
                    embedding = LLMEmbedding.embed(notice.supplier_profile, as_bytes=True)
                    if embedding:
                        NoticeDao.update_supplier_profile_embedding(notice.id, embedding)
                        success += 1
                        logger.info(f"[backfill] id={notice.id} 成功")
                    else:
                        failed += 1
                        logger.warning(f"[backfill] id={notice.id} 返回空向量")
                except Exception as e:
                    failed += 1
                    logger.error(f"[backfill] id={notice.id} 失败: {e}")

        logger.info(f"补算完成: 成功 {success} 条, 失败 {failed} 条, 跳过 {skipped} 条")

    # ---------------------------------------------------------------------------
    # 补算供应商 Embedding
    # ---------------------------------------------------------------------------
    @staticmethod
    def run_backfill_supplier(args):
        suppliers = SupplierDao.list_all()
        if not suppliers:
            logger.info("没有供应商记录")
            return

        success = failed = skipped = 0
        for supplier in suppliers:
            if supplier.profile_embedding and len(supplier.profile_embedding) > 0:
                skipped += 1
                continue

            try:
                embedding = LLMEmbedding.get_supplier_embedding(supplier)
                if embedding:
                    SupplierDao.update_embedding(supplier.id, embedding)
                    success += 1
                    logger.info(f"[backfill] supplier_id={supplier.id} {supplier.company_name} 成功")
                else:
                    failed += 1
                    logger.warning(f"[backfill] supplier_id={supplier.id} 返回空向量")
            except Exception as e:
                failed += 1
                logger.error(f"[backfill] supplier_id={supplier.id} 失败: {e}")

        logger.info(f"补算完成: 成功 {success} 条, 失败 {failed} 条, 跳过 {skipped} 条")
