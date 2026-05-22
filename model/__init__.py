"""数据模型包."""
from datetime import datetime

from sqlalchemy.orm import declarative_base

# 声明基类
Base = declarative_base()

_DEFAULT_DATETIME = datetime(1970, 1, 1, 0, 0, 0)

from model.procurement_notice import ProcurementNotice
from model.notice_qualification import NoticeQualification
from model.notice_attachment import NoticeAttachment
from model.notice_package import NoticePackage
from model.supplier_profile import SupplierProfile
from model.supplier_service_region import SupplierServiceRegion
from model.match_result import MatchResult
