"""用户路由 —— Controller 类实现."""

from datetime import datetime
from time import time
from fastapi import APIRouter, Depends, HTTPException
from api.schemas import (Res, FavoriteListReq, FavoriteListRes, FavoriteListItem, WxLoginReq, WxLoginRes)
from dao import UserDao, UserNoticeInteractionDao, NoticeDao
from models import UserDto
from providers import WeChat
from util import Auth


class UserController:
    """用户控制器."""

    def __init__(self):
        self.router = APIRouter(prefix="/user", tags=["User"])
        self.router.add_api_route("/wx_login", self.wx_login, methods=["POST"], response_model=Res[WxLoginRes])
        self.router.add_api_route("/favorites", self.get_user_favorites, methods=["POST"],
                                  response_model=Res[FavoriteListRes])

    @classmethod
    def wx_login(cls, req: WxLoginReq):
        """小程序微信登录.
        前端调用 wx.login() 获取 code 后传入，后端向微信换取 openid/unionid，
        自动完成用户注册（id 为当前时间戳秒级）并返回 JWT token。
        """
        login_res = WeChat.login(req.code)
        if login_res.get("errcode"):
            raise HTTPException(
                status_code=400,
                detail=login_res.get("errmsg", "微信登录失败"),
            )

        openid = login_res.get("openid", "")
        unionid = login_res.get("unionid", "")

        if not openid:
            raise HTTPException(status_code=400, detail="未能获取微信用户信息")

        # 查找或创建用户
        user = UserDao.get_by_oid(openid)
        if not user:
            user_id = int(time())
            user_dto = UserDto(
                user_id=user_id,
                platform=req.platform,
                wx_openid=openid,
                wx_unionid=unionid,
            )
            UserDao.create(user_dto)
            user = UserDao.get_by_uid(user_id)

        token = Auth.gen_token(user_id=user.user_id, platform=req.platform)

        return Res(
            data=WxLoginRes(
                token=token
            )
        )

    @classmethod
    def get_user_favorites(cls, req: FavoriteListReq, user: dict = Depends(Auth.user)):
        """获取用户收藏列表."""
        uid = user["user_id"]
        user = UserDao.get_by_uid(uid)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {uid}")

        interactions = UserNoticeInteractionDao.fetch_favorites(uid, limit=req.limit, offset=req.offset)
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
