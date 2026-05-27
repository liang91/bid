"""supplier_service_regions 表的数据访问对象（SQLAlchemy 2.0）."""

from typing import List

from loguru import logger

from sqlalchemy import delete, select

from models import SupplierServiceRegion

from dao import db


class SupplierServiceRegionDao:
    """供应商可服务地区存储器."""

    @staticmethod
    def get_regions_by_supplier(supplier_id: int) -> List[str]:
        """获取供应商服务的所有省份名称列表."""
        with db() as session:
            result = session.execute(
                select(SupplierServiceRegion.region_name)
                .where(SupplierServiceRegion.supplier_id == supplier_id)
            )
            return [row[0] for row in result.all()]

    @staticmethod
    def replace_regions(supplier_id: int, regions: List[str]) -> bool:
        """全量替换供应商的服务地区（先删除再插入）."""
        if not regions:
            return False
        with db.begin() as session:
            session.execute(
                delete(SupplierServiceRegion).where(
                    SupplierServiceRegion.supplier_id == supplier_id
                )
            )
            for region in regions:
                session.add(
                    SupplierServiceRegion(supplier_id=supplier_id, region_name=region)
                )
            return True

    @staticmethod
    def batch_get_regions(supplier_ids: List[int]) -> dict:
        """批量获取多个供应商的服务地区.

        Returns:
            {supplier_id: [region_name, ...]}
        """
        if not supplier_ids:
            return {}
        with db() as session:
            result = session.execute(
                select(SupplierServiceRegion.supplier_id, SupplierServiceRegion.region_name)
                .where(SupplierServiceRegion.supplier_id.in_(supplier_ids))
            )
            data = {}
            for sid, region_name in result.all():
                data.setdefault(sid, []).append(region_name)
            for sid in supplier_ids:
                data.setdefault(sid, [])
            return data
