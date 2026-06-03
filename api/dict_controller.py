"""字典路由 —— Controller 类实现."""

from fastapi import APIRouter

from api.schemas import Res, DictRes, DictItem


class DictController:
    """字典控制器."""

    _QUALIFICATIONS = [
        DictItem(code="DECORATION_L1", name="装修工程一级"),
        DictItem(code="DECORATION_L2", name="装修工程二级"),
        DictItem(code="SAFETY_LICENSE", name="安全生产许可证"),
        DictItem(code="FIRE_PROTECTION", name="消防设施工程"),
        DictItem(code="MECHATRONICS", name="机电安装工程"),
        DictItem(code="INTELLIGENCE", name="电子与智能化"),
        DictItem(code="CONSTRUCTOR", name="建造师"),
        DictItem(code="CURTAIN_WALL", name="建筑幕墙"),
        DictItem(code="STEEL_STRUCTURE", name="钢结构"),
    ]

    _BUSINESS_TYPES = [
        DictItem(code="OFFICE", name="办公室"),
        DictItem(code="RESTAURANT", name="餐饮"),
        DictItem(code="HOTEL", name="酒店"),
        DictItem(code="COMMERCIAL", name="商业空间"),
        DictItem(code="HOSPITAL", name="医院"),
        DictItem(code="SCHOOL", name="学校"),
        DictItem(code="FACTORY", name="厂房"),
        DictItem(code="EXHIBITION", name="展厅"),
    ]

    _REGIONS = [
        DictItem(code="BEIJING", name="北京"),
        DictItem(code="TIANJIN", name="天津"),
        DictItem(code="HEBEI", name="河北"),
        DictItem(code="SHANDONG", name="山东"),
        DictItem(code="SHANXI", name="山西"),
        DictItem(code="NEIMENGGU", name="内蒙古"),
    ]

    def __init__(self):
        self.router = APIRouter(prefix="/dict", tags=["Dict"])
        self.router.add_api_route(
            "", self.get_dict, methods=["POST"],
            response_model=Res[DictRes],
        )

    def get_dict(self):
        """获取所有字典枚举值."""
        return Res(
            data=DictRes(
                qualifications=self._QUALIFICATIONS,
                business_types=self._BUSINESS_TYPES,
                regions=self._REGIONS,
            )
        )
