"""supplier 表的数据访问对象（SQLAlchemy 2.0）."""

from sqlalchemy import select

from models import Supplier, SupplierDto

from dao import db


class SupplierDao:
    """供应商画像存储器."""

    @staticmethod
    def create(dto: SupplierDto) -> int:
        with db.begin() as session:
            profile = Supplier(**dto.model_dump())
            session.add(profile)
            session.flush()
            return profile.id

    @staticmethod
    def get_by_id(supplier_id: int) -> SupplierDto | None:
        """根据供应商ID查询供应商画像."""
        with db() as session:
            obj = session.get(Supplier, supplier_id)
            if not obj:
                return None
            return SupplierDto.model_validate(obj)

    @staticmethod
    def list_all() -> list[SupplierDto]:
        """查询所有供应商画像."""
        with db() as session:
            result = session.execute(select(Supplier))
            return [SupplierDto.model_validate(row) for row in result.scalars().all()]

    @staticmethod
    def update_embedding(supplier_id: int, embedding: list) -> bool:
        """更新供应商的 Embedding 向量."""
        with db.begin() as session:
            supplier = session.get(Supplier, supplier_id)
            if not supplier:
                return False
            supplier.profile_embedding = embedding
            return True
