"""供应商（设置）路由 —— Controller 类实现."""

from fastapi import APIRouter, Depends, HTTPException

from api.schemas import (
    Res,
    SupplierProfile,
    SupplierDictRes, DictItem,
)
from dao import SupplierDao, UserDao
from models import SupplierDto
from util.auth import Auth


class SupplierController:
    """供应商控制器."""

    def __init__(self):
        self.router = APIRouter(prefix="/suppliers", tags=["Suppliers"])
        self.router.add_api_route("/profile/dict", self.profile_dict, methods=["POST"],
                                  response_model=Res[SupplierDictRes])
        self.router.add_api_route("/profile/save", self.save_profile, methods=["POST"],
                                  response_model=Res[SupplierProfile])
        self.router.add_api_route("/profile/get", self.get_profile, methods=["POST"],
                                  response_model=Res[SupplierProfile])

    # ─────────────────────────────────────────
    # 字典数据（资质、地区）
    # ─────────────────────────────────────────
    qualifications = [
        # ── 装修核心 ──
        DictItem(code="DECORATION_L1", name="建筑装修装饰工程专业承包一级"),
        DictItem(code="DECORATION_L2", name="建筑装修装饰工程专业承包二级"),
        # ── 许可 ──
        DictItem(code="SAFETY_LICENSE", name="安全生产许可证"),
        # ── 总承包 ──
        DictItem(code="BUILDING_L1", name="建筑工程施工总承包一级"),
        DictItem(code="BUILDING_L2", name="建筑工程施工总承包二级"),
        DictItem(code="MUNICIPAL", name="市政公用工程施工总承包"),
        # ── 幕墙/钢结构 ──
        DictItem(code="CURTAIN_WALL", name="建筑幕墙工程专业承包"),
        DictItem(code="STEEL_STRUCTURE", name="钢结构工程专业承包"),
        # ── 机电消防智能化 ──
        DictItem(code="MECHATRONICS", name="机电安装工程专业承包"),
        DictItem(code="FIRE_PROTECTION", name="消防设施工程专业承包"),
        DictItem(code="INTELLIGENCE", name="电子与智能化工程专业承包"),
        # ── 防水保温环保 ──
        DictItem(code="WATERPROOF", name="防水防腐保温工程专业承包"),
        DictItem(code="ENVIRONMENT", name="环保工程专业承包"),
        # ── 照明/地基/特种 ──
        DictItem(code="LIGHTING", name="城市及道路照明工程专业承包"),
        DictItem(code="FOUNDATION", name="地基基础工程专业承包"),
        DictItem(code="SPECIAL", name="特种工程（结构补强）专业承包"),
        DictItem(code="SCAFFOLD", name="模板脚手架专业承包"),
    ]

    regions = [
        DictItem(code="BEIJING", name="北京"),
        DictItem(code="TIANJIN", name="天津"),
        DictItem(code="HEBEI", name="河北"),
    ]

    @classmethod
    def profile_dict(cls):
        """获取供应商字典数据：资质列表 + 京津冀地区列表."""
        return Res(
            data=SupplierDictRes(
                qualifications=cls.qualifications,
                regions=cls.regions,
            )
        )

    # ─────────────────────────────────────────
    # 供应商资料保存（创建或更新）
    # ─────────────────────────────────────────
    @classmethod
    def save_profile(cls, req: SupplierProfile, user: dict = Depends(Auth.user)):
        """保存供应商资料.

        新用户首次设置时自动创建供应商并绑定到当前账号；
        已绑定用户则更新现有供应商信息。
        """
        uid = user["user_id"]
        user = UserDao.get_by_uid(uid)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if user.supplier_id:
            # 更新现有供应商
            supplier = SupplierDao.get(user.supplier_id)
            if not supplier:
                raise HTTPException(status_code=404, detail="供应商不存在")
            supplier.company_name = req.company_name
            supplier.qualifications = req.qualifications
            supplier.min_budget = req.min_budget
            supplier.max_budget = req.max_budget
            supplier.service_regions = req.service_regions

            SupplierDao.update(supplier)
            supplier_id = user.supplier_id
        else:
            # 创建新供应商
            supplier_dto = SupplierDto(
                company_name=req.company_name,
                qualifications=req.qualifications,
                min_budget=req.min_budget,
                max_budget=req.max_budget,
                service_regions=req.service_regions,
            )
            supplier_id = SupplierDao.create(supplier_dto)
            # 绑定到当前用户
            user.supplier_id = supplier_id
            UserDao.update(user)

        req.supplier_id = supplier_id
        return Res(data=req)

    # ─────────────────────────────────────────
    # 获取供应商设置
    # ─────────────────────────────────────────
    @classmethod
    def get_profile(cls, user: dict = Depends(Auth.user)):
        """获取供应商偏好设置."""
        user = UserDao.get_by_uid(user['user_id'])
        if not user or not user.supplier_id:
            raise HTTPException(status_code=400, detail="缺少供应商ID")
        supplier = SupplierDao.get(user.supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail=f"供应商不存在: {user.supplier_id}")

        return Res(
            data=SupplierProfile(
                company_name=supplier.company_name or "",
                qualifications=supplier.qualifications,
                business_scopes=supplier.business_scopes,
                min_budget=supplier.min_budget,
                max_budget=supplier.max_budget,
                service_regions=supplier.service_regions or [],
            )
        )
