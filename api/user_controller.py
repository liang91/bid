"""用户路由 —— Controller 类实现."""

from datetime import datetime
from fastapi import APIRouter, HTTPException

from api.schemas import (
    Res,
    FavoriteListReq, FavoriteListRes, FavoriteListItem,
)
from dao import UserDao, UserNoticeInteractionDao, NoticeDao


class UserController:
    """用户控制器."""

    def __init__(self):
        self.router = APIRouter(prefix="/users", tags=["Users"])
        self.router.add_api_route(
            "/favorites", self.get_user_favorites, methods=["POST"],
            response_model=Res[FavoriteListRes],
        )

    def get_user_favorites(self, req: FavoriteListReq):
        """获取用户收藏列表."""
        user = UserDao.get(req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {req.user_id}")

        interactions = UserNoticeInteractionDao.fetch_favorites(req.user_id, limit=req.limit, offset=req.offset)
        notice_ids = [i.notice_id for i in interactions]

        notices = {}
        for nid in notice_ids:
            n = NoticeDao.get(nid)
            if n:
                notices[nid] = n

        data = []
        for inter in interactions:
            notice = notices.get(inter.notice_id)
            if not notice:
                continue

            v = int(notice.budget)
            if v >= 100000000:
                amount_display = f"¥{v // 100000000}亿"
            elif v >= 10000:
                amount_display = f"¥{v // 10000}万"
            else:
                amount_display = f"¥{v}"

            bid_deadline_str = "--"
            if notice.bid_deadline and notice.bid_deadline.year > 1970:
                bid_deadline_str = f"截标 {notice.bid_deadline.strftime('%m-%d')}"

            tags = []
            if notice.industry_tags:
                tags.extend(notice.industry_tags[:2])

            if notice.bid_deadline and notice.bid_deadline.year > 1970:
                days_left = (notice.bid_deadline - datetime.now()).days
                if days_left < 7:
                    tags.append(f"⚠️ 仅剩{days_left}天")

            data.append(FavoriteListItem(
                notice_id=notice.id or 0,
                title=notice.title or notice.project_name or "",
                amount_display=amount_display,
                meta={
                    "location": f"{notice.region_province or ''} · {notice.region_city or ''}",
                    "bid_deadline": bid_deadline_str,
                    "area": "--",
                },
                tags=tags,
            ))

        return Res(data=FavoriteListRes(total=len(data), data=data))
