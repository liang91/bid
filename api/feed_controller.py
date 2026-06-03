"""首页 Feed 路由 —— Controller 类实现."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.schemas import (
    Res,
    FeedReq, FeedRes, FeedItem, InfoGrid, Timeline, TimelineItem, Purchaser,
)
from dao import (
    NoticeDao, UserDao, SupplierDao, MatchDao,
    UserNoticeInteractionDao,
)


class FeedController:
    """Feed 推荐控制器."""

    def __init__(self):
        self.router = APIRouter(prefix="/feed", tags=["Feed"])
        self.router.add_api_route("list", self.list, methods=["POST"], response_model=Res[FeedRes])

    @staticmethod
    def _format_amount(value: Decimal) -> dict:
        """格式化金额."""
        v = int(value)
        if v >= 100000000:
            display = f"¥{v // 100000000}亿"
        elif v >= 10000:
            display = f"¥{v // 10000}万"
        else:
            display = f"¥{v}"
        return {"label": "预估金额", "value": v, "display": display}

    def _build_feed_item(self, notice, interaction: Optional[dict], match_score: float = 0) -> FeedItem:
        """将 NoticeDto 转换为 FeedItem."""
        score = int(match_score)
        level = "高" if score >= 90 else "中"

        amount = self._format_amount(notice.budget)

        info_grid = InfoGrid(
            location=f"{notice.region_province or ''}{notice.region_city or ''}{notice.region_district or ''}",
            area="--",
            duration="--",
            deposit={"value": "--", "alert": False},
        )

        now = datetime.now()
        bid_deadline_alert = False
        if notice.bid_deadline and notice.bid_deadline.year > 1970:
            days_left = (notice.bid_deadline - now).days
            bid_deadline_alert = days_left < 7
            bid_deadline_str = notice.bid_deadline.strftime("%m-%d")
        else:
            bid_deadline_str = "--"

        timeline = Timeline(
            register_deadline=TimelineItem(date="--", label="报名截止"),
            bid_deadline=TimelineItem(date=bid_deadline_str, label="截标日期", alert=bid_deadline_alert),
            open_date=TimelineItem(date="--", label="开标日期"),
        )

        qualifications = []
        if notice.qualification_summary:
            qualifications = [q.strip() for q in notice.qualification_summary.split("；") if q.strip()]
        if not qualifications:
            qualifications = ["详见公告原文"]

        tags = []
        if notice.industry_tags:
            tags.extend(notice.industry_tags[:2])
        if notice.sme_oriented:
            tags.append("中小企业")

        purchaser = Purchaser(
            name=notice.purchaser_name or "未知",
            avatar_text=(notice.purchaser_name or "招")[:1],
            sub=f"{notice.region_province or ''} · {notice.method or '公开招标'}",
        )

        is_urgent = bid_deadline_alert
        is_favorite = bool(interaction and interaction.get("is_favorite"))

        return FeedItem(
            notice_id=notice.id or 0,
            match_score=score,
            match_level=level,
            title=notice.title or notice.project_name or "",
            tags=tags,
            is_urgent=is_urgent,
            amount=amount,
            info_grid=info_grid,
            timeline=timeline,
            qualifications=qualifications,
            description=notice.abstract[:120] + "..." if notice.abstract and len(notice.abstract) > 120 else (
                    notice.abstract or ""),
            purchaser=purchaser,
            is_favorite=is_favorite,
        )

    def list(self, req: FeedReq):
        """获取推荐招标列表."""
        user = UserDao.get(req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {req.user_id}")

        supplier = SupplierDao.get(user.supplier_id) if user.supplier_id else None
        if not supplier:
            return Res(data=FeedRes(data=[], next_cursor=None, has_more=False))

        # 1. 硬规则粗筛
        candidates = NoticeDao.fetch_candidates(
            region_names=supplier.service_regions,
            min_budget=supplier.min_budget,
            max_budget=supplier.max_budget,
            limit=200,
        )
        if not candidates:
            return Res(data=FeedRes(data=[], next_cursor=None, has_more=False))

        # 2. 获取最近的匹配记录，提取 embedding 分数
        matches = MatchDao.fetch_latest_by_supplier(supplier.id or 0, day=date.today(), limit=3)
        score_map: dict[int, float] = {}
        for match in matches:
            if match.filtered_notices:
                for item in match.filtered_notices:
                    nid = getattr(item, "notice_id", 0)
                    sc = getattr(item, "score", 0.0)
                    if nid and sc > score_map.get(nid, 0):
                        score_map[nid] = sc * 100

        # 3. 排除不感兴趣的
        candidate_ids = [n.id for n in candidates if n.id]
        interactions = UserNoticeInteractionDao.fetch_interactions(req.user_id, candidate_ids)

        filtered = []
        for notice in candidates:
            nid = notice.id or 0
            inter = interactions.get(nid)
            if inter and inter.is_not_interested:
                continue
            filtered.append((notice, inter, score_map.get(nid, 0)))

        # 4. 按分数倒序
        filtered.sort(key=lambda x: x[2], reverse=True)

        # 5. 分页
        items = filtered[:req.limit]
        data = [self._build_feed_item(n, i, s) for n, i, s in items]

        return Res(
            data=FeedRes(
                data=data,
                next_cursor=req.cursor,
                has_more=len(filtered) > req.limit,
            )
        )
