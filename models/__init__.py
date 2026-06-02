"""数据模型包."""
from datetime import datetime

from sqlalchemy.orm import declarative_base

# 声明基类
Base = declarative_base()

_DEFAULT_DATETIME = datetime(1970, 1, 1, 0, 0, 0)

from models.notice import Notice, NoticeDto
from models.notice_qualification import NoticeQualification, NoticeQualificationDto
from models.notice_attachment import NoticeAttachment, NoticeAttachmentDto
from models.notice_package import NoticePackage, NoticePackageDto
from models.supplier import Supplier, SupplierDto, SupplierQualification
from models.supplier_service_region import SupplierServiceRegion, SupplierServiceRegionDto
from models.match import MatchNoticeScore, Match, MatchDto
from models.job_log import JobLog, JobLogDto
from models.site import Site, SiteDto
from models.user import User, UserDto
