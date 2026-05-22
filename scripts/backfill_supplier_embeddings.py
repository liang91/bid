#!/usr/bin/env python3
"""为存量供应商计算 Embedding 向量.

用法:
    python scripts/backfill_supplier_embeddings.py

说明:
    扫描 supplier_profiles 表中 business_embedding IS NULL 的记录，
    调用 Embedding API 计算向量并回写数据库。
"""
import logging
import sys

sys.path.insert(0, ".")

from dao import SupplierProfileDao
from services.embedding_service import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    dao = SupplierProfileDao()

    suppliers = dao.list_all()
    if not suppliers:
        logger.info("没有供应商记录")
        return

    success = failed = skipped = 0
    for supplier in suppliers:
        # 如果已有 embedding 且非空，跳过
        if supplier.business_embedding and len(supplier.business_embedding) > 0:
            skipped += 1
            continue

        try:
            embedding = EmbeddingService.get_supplier_embedding(supplier)
            if embedding:
                dao.update_embedding(supplier.id, embedding)
                success += 1
                logger.info(f"[backfill] supplier_id={supplier.id} {supplier.company_name} 成功")
            else:
                failed += 1
                logger.warning(f"[backfill] supplier_id={supplier.id} 返回空向量")
        except Exception as e:
            failed += 1
            logger.error(f"[backfill] supplier_id={supplier.id} 失败: {e}")

    logger.info(
        f"补算完成: 成功 {success} 条, 失败 {failed} 条, 跳过 {skipped} 条"
    )


if __name__ == "__main__":
    main()
