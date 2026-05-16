#!/usr/bin/env python3
"""将历史 JSON 数据导入 MySQL.

用法:
    python scripts/import_json_to_mysql.py data/ccgp_bids_20260515_170419.json
    python scripts/import_json_to_mysql.py data/*.json

环境变量（或修改下方默认值）:
    MYSQL_HOST      默认 localhost
    MYSQL_PORT      默认 3306
    MYSQL_USER      默认 root
    MYSQL_PASSWORD  默认空
    MYSQL_DATABASE  默认 bid_service
"""

import json
import os
import sys
from pathlib import Path

# 将项目根目录加入路径，以便导入 crawlers 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.db_storage import MySQLStorage
from crawlers.models import BidNotice


def load_notices_from_json(filepath: str) -> list[BidNotice]:
    """从 JSON 文件加载公告列表."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"[跳过] {filepath} 内容不是数组")
        return []

    notices = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            notice = BidNotice(**item)
            notices.append(notice)
        except Exception as e:
            print(f"[解析失败] 跳过一条记录: {e}")
    return notices


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # 读取数据库连接配置
    storage = MySQLStorage(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "bid_service"),
    )

    total_inserted = total_updated = total_failed = 0

    for pattern in sys.argv[1:]:
        # 支持通配符
        paths = list(Path(".").glob(pattern))
        if not paths:
            print(f"[警告] 未找到匹配文件: {pattern}")
            continue

        for filepath in paths:
            if not filepath.is_file():
                continue

            print(f"\n[读取] {filepath}")
            notices = load_notices_from_json(str(filepath))
            if not notices:
                continue

            print(f"[导入] 共 {len(notices)} 条记录...")
            result = storage.save_notices(notices)
            print(
                f"[结果] 新增: {result['inserted']}, "
                f"更新: {result['updated']}, "
                f"失败: {result['failed']}"
            )
            total_inserted += result["inserted"]
            total_updated += result["updated"]
            total_failed += result["failed"]

    print("\n" + "=" * 50)
    print(f"全部导入完成: 新增 {total_inserted}, 更新 {total_updated}, 失败 {total_failed}")
    print("=" * 50)


if __name__ == "__main__":
    main()
