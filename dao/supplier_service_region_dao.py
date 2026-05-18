"""supplier_service_regions 表的数据访问对象."""

import logging
from typing import List

from .base import BaseStorage

logger = logging.getLogger(__name__)


class SupplierServiceRegionDao(BaseStorage):
    """供应商可服务地区存储器."""

    def __init__(self, conn_params: dict):
        super().__init__(conn_params)

    def get_regions_by_supplier(self, supplier_id: int) -> List[str]:
        """获取供应商服务的所有省份名称列表."""
        sql = "SELECT region_name FROM supplier_service_regions WHERE supplier_id = %s"
        with self._get_cursor() as cursor:
            cursor.execute(sql, (supplier_id,))
            return [row["region_name"] for row in cursor.fetchall()]

    def replace_regions(self, supplier_id: int, regions: List[str]) -> bool:
        """全量替换供应商的服务地区（先删除再插入）."""
        if not regions:
            return False
        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM supplier_service_regions WHERE supplier_id = %s",
                (supplier_id,),
            )
            sql = "INSERT INTO supplier_service_regions (supplier_id, region_name) VALUES (%s, %s)"
            cursor.executemany(sql, [(supplier_id, r) for r in regions])
            return True

    def batch_get_regions(self, supplier_ids: List[int]) -> dict:
        """批量获取多个供应商的服务地区.

        Returns:
            {supplier_id: [region_name, ...]}
        """
        if not supplier_ids:
            return {}
        result = {sid: [] for sid in supplier_ids}
        placeholders = ", ".join(["%s"] * len(supplier_ids))
        sql = f"SELECT supplier_id, region_name FROM supplier_service_regions WHERE supplier_id IN ({placeholders})"
        with self._get_cursor() as cursor:
            cursor.execute(sql, tuple(supplier_ids))
            for row in cursor.fetchall():
                result[row["supplier_id"]].append(row["region_name"])
        return result
