"""招标公告详情路由 —— Controller 类实现."""

from datetime import datetime
from fastapi import APIRouter, HTTPException

from api.schemas import (
    Res,
    NoticeDetailRes, NoticeDetailReq, FavoriteReq, FavoriteRes,
    NotInterestedReq,
)
from dao import NoticeDao, UserDao, UserNoticeInteractionDao


class NoticeController:
    """招标公告控制器."""

    def __init__(self):
        self.router = APIRouter(prefix="/notices", tags=["Notices"])
        self.router.add_api_route(
            "/detail", self.get_notice_detail, methods=["POST"],
            response_model=Res[NoticeDetailRes],
        )
        self.router.add_api_route(
            "/favorite", self.toggle_favorite, methods=["POST"],
            response_model=Res[FavoriteRes],
        )
        self.router.add_api_route(
            "/not-interested", self.mark_not_interested, methods=["POST"],
            response_model=Res[dict],
        )

    def get_notice_detail(self, req: NoticeDetailReq):
        """获取招标详情."""
        notice = NoticeDao.get(req.notice_id)
        if not notice:
            raise HTTPException(status_code=404, detail=f"公告不存在: {req.notice_id}")

        is_favorite = False
        if req.user_id:
            inter = UserNoticeInteractionDao.get(req.user_id, req.notice_id)
            if inter:
                is_favorite = bool(inter.is_favorite)
            UserNoticeInteractionDao.mark_viewed(req.user_id, req.notice_id)

        v = int(notice.budget)
        if v >= 100000000:
            amount_display = f"¥{v // 100000000}亿"
        elif v >= 10000:
            amount_display = f"¥{v // 10000}万"
        else:
            amount_display = f"¥{v}"

        bid_deadline_alert = False
        bid_deadline_display = "--"
        if notice.bid_deadline and notice.bid_deadline.year > 1970:
            days_left = (notice.bid_deadline - datetime.now()).days
            bid_deadline_alert = days_left < 7
            bid_deadline_display = f"⏰ {notice.bid_deadline.strftime('%Y-%m-%d')}（{days_left}天后）" if days_left > 0 else f"⏰ {notice.bid_deadline.strftime('%Y-%m-%d')}（今日截标）"

        qualifications = []
        if notice.qualification_summary:
            qualifications = [q.strip() for q in notice.qualification_summary.split("；") if q.strip()]
        if not qualifications:
            qualifications = ["详见公告原文"]

        return Res(
            data=NoticeDetailRes(
                notice_id=req.notice_id,
                title=notice.title or notice.project_name or "",
                tags=notice.industry_tags or [],
                amount={"value": v, "display": amount_display},
                hero_meta={
                    "location": f"{notice.region_province or ''}{notice.region_city or ''}",
                    "bid_deadline": {
                        "date": notice.bid_deadline.strftime("%Y-%m-%d") if notice.bid_deadline and notice.bid_deadline.year > 1970 else "--",
                        "display": bid_deadline_display,
                        "alert": bid_deadline_alert,
                    },
                },
                overview={
                    "project_type": "、".join(notice.industry_tags[:2]) if notice.industry_tags else "装修工程",
                    "area": "--",
                    "duration": "--",
                    "method": notice.method or "公开招标",
                    "deposit": "--",
                },
                qualifications=qualifications,
                description=notice.abstract or "",
                purchaser={
                    "name": notice.purchaser_name or "未知",
                    "sub": f"{notice.region_province or ''} / {notice.method or '公开招标'}",
                    "avatar_text": (notice.purchaser_name or "招")[:1],
                },
                contacts={
                    "purchaser_contact_person": notice.purchaser_contact_person or "",
                    "purchaser_contact_phone": notice.purchaser_contact_phone or "",
                    "agency_contact_person": notice.agency_contact_person or "",
                    "agency_contact_phone": notice.agency_contact_phone or "",
                },
                attachments=[],
                is_favorite=is_favorite,
            )
        )

    def toggle_favorite(self, req: FavoriteReq):
        """收藏/取消收藏."""
        notice = NoticeDao.get(req.notice_id)
        if not notice:
            raise HTTPException(status_code=404, detail=f"公告不存在: {req.notice_id}")

        user = UserDao.get(req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {req.user_id}")

        is_fav = 1 if req.action == "add" else 0
        UserNoticeInteractionDao.upsert_favorite(req.user_id, req.notice_id, is_fav)

        return Res(data=FavoriteRes(success=True, is_favorite=bool(is_fav)))

    def mark_not_interested(self, req: NotInterestedReq):
        """标记不感兴趣."""
        notice = NoticeDao.get(req.notice_id)
        if not notice:
            raise HTTPException(status_code=404, detail=f"公告不存在: {req.notice_id}")

        user = UserDao.get(req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {req.user_id}")

        UserNoticeInteractionDao.upsert_not_interested(req.user_id, req.notice_id)
        return Res(data={"is_not_interested": True})
