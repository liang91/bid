#!/usr/bin/env python3
"""为存量已解析公告补算 Embedding 向量.

用法:
    python scripts/backfill_notice_embeddings.py [--batch 50]

说明:
    扫描 procurement_notices 表中 status=30 且 category_embedding IS NULL 的记录，
    调用 Embedding API 计算向量并回写数据库。
"""
import argparse
import logging
import sys

sys.path.insert(0, ".")

from config import load_config
from dao import ProcurementNoticeDao
from services.embedding_service import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="补算公告 Embedding 向量")
    parser.add_argument("--batch", type=int, default=50, help="每批处理条数")
    parser.add_argument("--limit", type=int, default=0, help="最大处理条数（0=无限制）")
    args = parser.parse_args()

    load_config()
    dao = ProcurementNoticeDao.instance()

    # 查询待补算的公告
    sql = """
        SELECT id FROM procurement_notices
        WHERE status = 30 AND (category_embedding IS NULL OR JSON_LENGTH(category_embedding) = 0)
        ORDER BY id DESC
    """
    if args.limit > 0:
        sql += f" LIMIT {args.limit}"

    rows = dao.execute(sql)
    notice_ids = [row["id"] for row in rows]
    if not notice_ids:
        logger.info("没有待补算 Embedding 的公告")
        return

    logger.info(f"待补算公告共 {len(notice_ids)} 条")

    success = failed = skipped = 0
    for i in range(0, len(notice_ids), args.batch):
        batch_ids = notice_ids[i : i + args.batch]
        # 批量查询完整公告数据
        placeholders = ", ".join(["%s"] * len(batch_ids))
        sql = f"SELECT * FROM procurement_notices WHERE id IN ({placeholders})"
        notice_rows = dao.execute(sql, tuple(batch_ids))

        for row in notice_rows:
            notice = dao._from_row(row)
            if not notice.project_name and not notice.title:
                skipped += 1
                continue
            try:
                embedding = EmbeddingService.get_notice_embedding(notice)
                if embedding:
                    dao.update_embedding(notice.id, embedding)
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
