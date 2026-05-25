#!/usr/bin/env python3
"""为存量已解析公告补算 supplier_profile_embedding 向量.

用法:
    python scripts/backfill_notice_embeddings.py [--batch 50]

说明:
    扫描 procurement_notices 表中 status=30 且 supplier_profile_embedding 为空的记录，
    调用 Embedding API 计算向量并回写数据库。
"""
import argparse
import sys

from loguru import logger

sys.path.insert(0, ".")

from sqlalchemy import select

from config import load_config
from dao import ProcurementNoticeDao
from dao import db
from model import ProcurementNotice
from services.embedding_service import EmbeddingService


def main():
    parser = argparse.ArgumentParser(description="补算公告 supplier_profile_embedding 向量")
    parser.add_argument("--batch", type=int, default=50, help="每批处理条数")
    parser.add_argument("--limit", type=int, default=0, help="最大处理条数（0=无限制）")
    args = parser.parse_args()

    load_config()

    # 查询待补算的公告（supplier_profile_embedding 为空且 supplier_profile 不为空）
    with db() as session:
        stmt = (
            select(ProcurementNotice.id)
            .where(
                ProcurementNotice.status == 30,
                ProcurementNotice.supplier_profile.isnot(None),
                ProcurementNotice.supplier_profile != "",
                ProcurementNotice.supplier_profile_embedding.is_(None),
            )
            .order_by(ProcurementNotice.id.desc())
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
        batch_ids = notice_ids[i : i + args.batch]

        with db() as session:
            notices = session.execute(
                select(ProcurementNotice).where(ProcurementNotice.id.in_(batch_ids))
            ).scalars().all()

        for notice in notices:
            if not notice.supplier_profile:
                skipped += 1
                continue
            try:
                embedding = EmbeddingService.embed(notice.supplier_profile, as_bytes=True)
                if embedding:
                    ProcurementNoticeDao.update_supplier_profile_embedding(notice.id, embedding)
                    success += 1
                    logger.info(f"[backfill] id={notice.id} 成功")
                else:
                    failed += 1
                    logger.warning(f"[backfill] id={notice.id} 返回空向量")
            except Exception as e:
                failed += 1
                logger.error(f"[backfill] id={notice.id} 失败: {e}")

    logger.info(
        f"补算完成: 成功 {success} 条, 失败 {failed} 条, 跳过 {skipped} 条"
    )


if __name__ == "__main__":
    main()
