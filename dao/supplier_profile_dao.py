"""supplier_profiles 表的数据访问对象（SQLAlchemy 2.0）."""

import logging
from typing import List, Optional

from sqlalchemy import select

from model import SupplierProfile

from .base import session_scope

logger = logging.getLogger(__name__)


class SupplierProfileDao:
    """供应商画像存储器."""

    def get_by_id(self, id: int) -> Optional[SupplierProfile]:
        """根据供应商ID查询供应商画像."""
        with session_scope() as session:
            return session.get(SupplierProfile, id)

    def list_all(self) -> List[SupplierProfile]:
        """查询所有供应商画像."""
        with session_scope() as session:
            result = session.execute(select(SupplierProfile))
            return list(result.scalars().all())

    def update_embedding(self, supplier_id: int, embedding: List[float]) -> bool:
        """更新供应商的 Embedding 向量."""
        with session_scope() as session:
            supplier = session.get(SupplierProfile, supplier_id)
            if not supplier:
                return False
            supplier.business_embedding = embedding
            session.commit()
            return True
