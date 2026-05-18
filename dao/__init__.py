"""数据访问对象包 —— SQLAlchemy 2.0 ORM 封装.

使用方式：
    from dao import ProcurementNoticeDao
    dao = ProcurementNoticeDao()
    dao.insert_list(notice_list)
"""
# 包导入时触发 engine 延迟初始化
from .base import init_engine  # noqa: F401

init_engine()

# 导出各表 DAO 类
from .procurement_notice_dao import ProcurementNoticeDao  # noqa: E402
from .notice_attachment_dao import NoticeAttachmentDao  # noqa: E402
from .notice_package_dao import NoticePackageDao  # noqa: E402
from .notice_qualification_dao import NoticeQualificationDao  # noqa: E402
from .supplier_profile_dao import SupplierProfileDao  # noqa: E402
from .supplier_service_region_dao import SupplierServiceRegionDao  # noqa: E402

__all__ = [
    "ProcurementNoticeDao",
    "NoticeAttachmentDao",
    "NoticePackageDao",
    "NoticeQualificationDao",
    "SupplierProfileDao",
    "SupplierServiceRegionDao",
]
