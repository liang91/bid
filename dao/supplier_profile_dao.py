"""supplier_profiles 表的数据访问对象（SQLAlchemy 2.0）."""

from typing import List, Optional

from loguru import logger

from sqlalchemy import select

from model import SupplierProfile
from model.supplier_profile import SupplierProfileDto

from dao import db, orm_to_dto



class SupplierProfileDao:
    """供应商画像存储器."""

    @staticmethod
    def get_by_id(id: int) -> Optional[SupplierProfileDto]:
        """根据供应商ID查询供应商画像."""
        with db() as session:
            obj = session.get(SupplierProfile, id)
            if not obj:
                return None
            return orm_to_dto(obj, SupplierProfileDto)

    @staticmethod
    def list_all() -> List[SupplierProfileDto]:
        """查询所有供应商画像."""
        with db() as session:
            result = session.execute(select(SupplierProfile))
            return [orm_to_dto(row, SupplierProfileDto) for row in result.scalars().all()]

    @staticmethod
    def update_embedding(supplier_id: int, embedding: list) -> bool:
        """更新供应商的 Embedding 向量."""
        with db.begin() as session:
            supplier = session.get(SupplierProfile, supplier_id)
            if not supplier:
                return False
            supplier.business_embedding = embedding
            return True
