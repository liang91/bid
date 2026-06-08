"""数据模型包."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator
from pydantic_core import PydanticUndefined
from sqlalchemy.orm import declarative_base

# 声明基类
Base = declarative_base()

_DEFAULT_DATETIME = datetime(1970, 1, 1, 0, 0, 0)


class DefaultDto(BaseModel):
    """为所有 DTO 提供 null/空字符串自动回退到默认值的能力."""

    @model_validator(mode="before")
    @classmethod
    def _set_defaults_for_nulls_and_blanks(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field_name, field_info in cls.model_fields.items():
            if field_name not in data:
                continue
            val = data[field_name]
            if val is None or val == "":
                default = field_info.default
                if default is PydanticUndefined and field_info.default_factory:
                    default = field_info.default_factory()
                if default is not PydanticUndefined:
                    data[field_name] = default
        return data


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
from models.user_notice_interaction import UserNoticeInteraction, UserNoticeInteractionDto
from models.latest_url import LatestUrl, LatestUrlDto
