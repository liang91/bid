"""供应商（设置）路由 —— Controller 类实现."""

from fastapi import APIRouter, HTTPException

from api.schemas import (
    Res,
    SupplierSettings, SupplierSettingsReq, SupplierSettingsUpdateReq,
)
from dao import SupplierDao


class SupplierController:
    """供应商控制器."""

    def __init__(self):
        self.router = APIRouter(prefix="/suppliers", tags=["Suppliers"])
        self.router.add_api_route(
            "/settings", self.get_supplier_settings, methods=["POST"],
            response_model=Res[SupplierSettings],
        )
        self.router.add_api_route(
            "/settings/update", self.update_supplier_settings, methods=["POST"],
            response_model=Res[dict],
        )

    @staticmethod
    def _format_amount_display(min_val: int, max_val: int) -> str:
        """格式化金额范围显示."""
        def _fmt(v: int) -> str:
            if v >= 100000000:
                return f"{v // 100000000}亿"
            elif v >= 10000:
                return f"{v // 10000}万"
            elif v == 0:
                return "不限"
            else:
                return f"{v}"
        return f"{_fmt(min_val)} - {_fmt(max_val)}"

    def get_supplier_settings(self, req: SupplierSettingsReq):
        """获取供应商偏好设置."""
        supplier = SupplierDao.get(req.supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail=f"供应商不存在: {req.supplier_id}")

        callable_qualifications = []
        if supplier.qualification_summary:
            callable_qualifications = [q.strip() for q in supplier.qualification_summary.split(",") if q.strip()]

        business_types = []
        if supplier.business_scope:
            business_types = [b.strip() for b in supplier.business_scope.split(",") if b.strip()]

        return Res(
            data=SupplierSettings(
                callable_qualifications=callable_qualifications,
                business_types=business_types,
                amount_range={
                    "min": int(supplier.min_budget),
                    "max": int(supplier.max_budget),
                    "display": self._format_amount_display(int(supplier.min_budget), int(supplier.max_budget)),
                },
                service_regions=supplier.service_regions or [],
            )
        )

    def update_supplier_settings(self, req: SupplierSettingsUpdateReq):
        """更新供应商偏好设置."""
        supplier = SupplierDao.get(req.supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail=f"供应商不存在: {req.supplier_id}")

        supplier.qualification_summary = ",".join(req.callable_qualifications)
        supplier.business_scope = ",".join(req.business_types)
        supplier.min_budget = req.min_budget
        supplier.max_budget = req.max_budget
        supplier.service_regions = req.service_regions

        success = SupplierDao.update(supplier)
        if not success:
            raise HTTPException(status_code=500, detail="更新失败")

        return Res(data={"updated": True})
