"""匹配结果推送服务 —— 方案A：混合推送模式.

核心流程：
1. 系统调用 add_msg_template 创建企业群发素材
2. 员工在企微APP「客户联系-待发送」中收到提醒
3. 员工点击「确认发送」后，消息到达供应商老板的个人微信
4. 企微推送 send_success / send_fail 回调，系统更新发送状态

推送状态（push_status）：
  0 = 未推送
  10 = 已创建群发素材（待员工确认）
  1 = 已送达（收到企微 send_success 回调）
  2 = 失败（创建素材失败 或 收到 send_fail 回调）
"""

from datetime import date
from loguru import logger

from config.loader import config
from dao import MatchDao, SupplierDao, NoticeDao, UserDao
from models import Match
from providers import WechatWorkClient


class PushService:
    """招标公告推荐推送服务（方案A：员工确认后发送）."""

    _client: WechatWorkClient | None = None
    _channel: str = "wechat_work"

    # push_status 状态常量
    STATUS_UNPUSHED = 0
    STATUS_PENDING_CONFIRM = 10
    STATUS_DELIVERED = 1
    STATUS_FAILED = 2

    @classmethod
    def _get_client(cls) -> WechatWorkClient:
        """懒加载企微客户端."""
        if cls._client is None:
            wc_cfg = config.get("wechat_work", {})
            cls._client = WechatWorkClient(
                corp_id=wc_cfg.get("corp_id", ""),
                corp_secret=wc_cfg.get("corp_secret", ""),
            )
        return cls._client

    # ─────────────────────────────────────────
    # 公开：单条推送 / 批量推送
    # ─────────────────────────────────────────
    @classmethod
    def create_group_msg_for_user(cls, match: Match, user_id: int) -> str | None:
        """为指定人员创建企业群发素材.

        Args:
            match: Match ORM 对象（含AI匹配结果）
            user_id: 目标人员ID

        Returns:
            msgid: 群发素材ID（创建成功）
            None: 创建失败或人员未绑定企微
        """
        user = UserDao.get(user_id)
        if not user:
            logger.warning(f"[Push] user_id={user_id} 不存在")
            return None

        if not user.wechat_external_userid or not user.wechat_follow_user_id:
            logger.warning(
                f"[Push] user_id={user_id} 未绑定企微，跳过"
            )
            return None

        # 构建消息内容
        text_content, link_title, link_desc, link_url = cls._build_message(match)

        try:
            msgid = cls._get_client().add_group_msg_template(
                sender=user.wechat_follow_user_id,
                external_userids=[user.wechat_external_userid],
                text_content=text_content,
                link_title=link_title,
                link_url=link_url,
                link_desc=link_desc,
            )
            logger.info(
                f"[Push] 创建群发素材成功: match_id={match.id}, user_id={user_id}, "
                f"msgid={msgid}"
            )
            return msgid
        except Exception as e:
            logger.error(
                f"[Push] 创建群发素材失败: match_id={match.id}, user_id={user_id}, err={e}"
            )
            return None

    @classmethod
    def push_match_to_supplier_users(cls, match: Match) -> dict:
        """为供应商下所有已绑定企微的人员创建群发素材.

        Returns:
            {"total": x, "success": y, "failed": z, "msgids": [...]}
        """
        users = UserDao.get_wechat_bound_users(match.supplier_id)
        if not users:
            logger.info(
                f"[Push] supplier_id={match.supplier_id} 无可推送人员"
            )
            return {"total": 0, "success": 0, "failed": 0, "msgids": []}

        total = len(users)
        success = 0
        msgids = []

        for user in users:
            msgid = cls.create_group_msg_for_user(match, user.id)
            if msgid:
                success += 1
                msgids.append(msgid)

        failed = total - success
        logger.info(
            f"[Push] match_id={match.id} 素材创建完成: "
            f"成功 {success}/{total}, msgids={msgids}"
        )
        return {"total": total, "success": success, "failed": failed, "msgids": msgids}

    @classmethod
    def push_daily_top_matches(cls, day: date | None = None) -> dict:
        """批量推送当天所有高匹配结果（创建群发素材，待员工确认）.

        调度任务调用入口。

        Returns:
            {"match_total": x, "user_total": y, "success": z}
        """
        day = day or date.today()
        matches = MatchDao.get_unpushed_top_matches(day=day, limit=200)
        if not matches:
            logger.info(f"[Push] {day} 无待推送匹配记录")
            return {"match_total": 0, "user_total": 0, "success": 0}

        logger.info(f"[Push] {day} 待推送匹配记录: {len(matches)} 条")

        match_total = 0
        user_total = 0
        success_total = 0

        for match in matches:
            result = cls.push_match_to_supplier_users(match)
            match_total += 1
            user_total += result["total"]
            success_total += result["success"]

            # 状态更新策略：
            # - 只要有一个素材创建成功，标记为「待员工确认」(10)
            # - 全部失败，标记为「失败」(2)
            if result["success"] > 0:
                MatchDao.update_push_status(
                    match_id=match.id,
                    status=cls.STATUS_PENDING_CONFIRM,
                    channel=cls._channel,
                    message_id=result["msgids"][0] if result["msgids"] else "",
                )
            else:
                MatchDao.update_push_status(
                    match_id=match.id,
                    status=cls.STATUS_FAILED,
                    channel=cls._channel,
                )

        logger.info(
            f"[Push] {day} 批量素材创建完成: "
            f"matches={match_total}, users={user_total}, success={success_total}"
        )
        return {
            "match_total": match_total,
            "user_total": user_total,
            "success": success_total,
        }

    # ─────────────────────────────────────────
    # 企微回调：更新发送结果
    # ─────────────────────────────────────────
    @classmethod
    def handle_send_result_callback(cls, msgid: str, success: bool, err_msg: str = ""):
        """处理企微群发结果回调.

        员工确认发送后，企微会推送事件到回调URL：
          - send_success: 成员发送成功
          - send_fail: 成员发送失败

        Args:
            msgid: 群发素材ID
            success: 是否发送成功
            err_msg: 失败原因（仅 success=False 时有效）
        """
        status = cls.STATUS_DELIVERED if success else cls.STATUS_FAILED
        # 通过 msgid 查找对应的 match 并更新状态
        # 注意：当前 schema 中 match.push_message_id 是 VARCHAR(128)
        # 如果一条 match 推给多个人，只记录了第一个 msgid
        # 精确追踪需要新增 match_user_pushes 表（后续可按需扩展）
        logger.info(
            f"[PushCallback] msgid={msgid}, success={success}, err={err_msg}"
        )

    # ─────────────────────────────────────────
    # 消息内容构建
    # ─────────────────────────────────────────
    @classmethod
    def _build_message(cls, match: Match) -> tuple[str, str, str, str]:
        """构建 link 类型消息内容.

        Returns:
            (text_content, link_title, link_desc, link_url)
        """
        notice = NoticeDao.get(match.notice_id)
        supplier = SupplierDao.get(match.supplier_id)

        # 供应商公司名称（用于个性化）
        company_name = supplier.company_name if supplier else ""

        # 前置引导文本
        text_content = (
            f"{company_name}您好，为您推荐一条匹配度较高的招标公告，"
            f"请点击下方卡片查看详情。"
        )

        # link 标题
        level_str = match.ai_match_level or "高"
        notice_title = notice.title if notice else "招标公告推荐"
        link_title = f"🎯 {level_str}匹配度 | {notice_title}"
        # 企微 link 标题限制，截断处理
        if len(link_title) > 64:
            link_title = link_title[:61] + "..."

        # link 描述（纯文本，不超过128字）
        desc_parts = []
        if match.ai_match_score:
            desc_parts.append(f"AI评分{match.ai_match_score}分")
        if match.ai_recommendation:
            rec = match.ai_recommendation
            if len(rec) > 40:
                rec = rec[:37] + "..."
            desc_parts.append(rec)
        if notice and notice.budget and notice.budget > 0:
            desc_parts.append(f"预算{notice.budget}元")
        if notice and notice.bid_deadline and notice.bid_deadline.year > 1970:
            desc_parts.append(f"截止{notice.bid_deadline.strftime('%m-%d')}")

        link_desc = " | ".join(desc_parts)
        if len(link_desc) > 128:
            link_desc = link_desc[:125] + "..."

        # 跳转 URL
        base_url = config.get("push", {}).get("detail_base_url", "")
        if base_url and notice:
            link_url = f"{base_url.rstrip('/')}/match/{match.id}?notice_id={notice.id}"
        else:
            link_url = notice.url if notice else ""

        return text_content, link_title, link_desc, link_url
