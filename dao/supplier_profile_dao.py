"""supplier_profiles 表的数据访问对象."""

import json
import logging
from typing import List, Optional

from model import SupplierProfile

from .base import BaseStorage

logger = logging.getLogger(__name__)


class SupplierProfileDao(BaseStorage):
    """供应商画像存储器."""

    def __init__(self, conn_params: dict):
        super().__init__(conn_params)

    def get_by_id(self, id: int) -> Optional[SupplierProfile]:
        """根据供应商ID查询供应商画像."""
        sql = "SELECT * FROM supplier_profiles WHERE id = %s"
        with self._get_cursor() as cursor:
            cursor.execute(sql, (id,))
            row = cursor.fetchone()
            return self._from_row(row) if row else None

    def list_all(self) -> List[SupplierProfile]:
        """查询所有供应商画像."""
        sql = "SELECT * FROM supplier_profiles"
        with self._get_cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [self._from_row(row) for row in rows]

    def update_embedding(self, supplier_id: int, embedding: List[float]) -> bool:
        """更新供应商的 Embedding 向量."""
        sql = "UPDATE supplier_profiles SET business_embedding = %s WHERE id = %s"
        with self._get_cursor() as cursor:
            cursor.execute(sql, (json.dumps(embedding), supplier_id))
            return cursor.rowcount > 0

    @staticmethod
    def _from_row(row: dict) -> SupplierProfile:
        """将数据库查询结果行转换为 SupplierProfile 实例."""
        profile = SupplierProfile()
        for key, val in row.items():
            if not hasattr(profile, key):
                continue
            if val is None:
                continue

            if key == "qualifications":
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        val = []
                elif not isinstance(val, list):
                    val = []

            if key == "business_embedding":
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        val = []
                elif not isinstance(val, list):
                    val = []

            if key in ("id", "joint_bid_willing", "sme_status", "ca_ready"):
                val = int(val) if val is not None else 0

            setattr(profile, key, val)
        return profile
