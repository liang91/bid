"""supplier_profiles 表的数据访问对象（SQLAlchemy 2.0）."""

import logging
from typing import List, Optional

from sqlalchemy import select

from model import SupplierProfile

from dao import db

logger = logging.getLogger(__name__)


class SupplierProfileDao:
    """供应商画像存储器."""

    @staticmethod
    def get_by_id(id: int) -> Optional[SupplierProfile]:
        """根据供应商ID查询供应商画像."""
        with db() as session:
            return session.get(SupplierProfile, id)

    @staticmethod
    def list_all() -> List[SupplierProfile]:
        """查询所有供应商画像."""
        with db() as session:
            result = session.execute(select(SupplierProfile))
            return list(result.scalars().all())

    @staticmethod
    def update_embedding(supplier_id: int, embedding: List[float]) -> bool:
        """更新供应商的 Embedding 向量."""
        with db.begin() as session:
            supplier = session.get(SupplierProfile, supplier_id)
            if not supplier:
                return False
            supplier.business_embedding = embedding
            return True
