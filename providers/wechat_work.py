"""企业微信客户联系（External Contact）客户端.

方案A：混合推送模式
- 系统调用 add_msg_template 创建群发素材
- 员工在企微APP点击「确认发送」后，消息到达客户个人微信
- 支持接收企微回调追踪发送结果
"""

import time

import requests
from loguru import logger


class WechatWorkClient:
    """企业微信客户联系 API 客户端."""

    BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self, corp_id: str, corp_secret: str):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    # ─────────────────────────────────────────
    # AccessToken 管理
    # ─────────────────────────────────────────
    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        url = f"{self.BASE_URL}/gettoken"
        resp = requests.get(
            url,
            params={"corpid": self.corp_id, "corpsecret": self.corp_secret},
            timeout=10,
        )
        data = resp.json()

        if data.get("errcode") != 0:
            raise RuntimeError(f"获取 access_token 失败: {data}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"]
        return self._access_token

    # ─────────────────────────────────────────
    # 方案A核心：创建企业群发素材
    # ─────────────────────────────────────────
    def add_group_msg_template(
        self,
        sender: str,
        external_userids: list[str],
        text_content: str = "",
        link_title: str = "",
        link_url: str = "",
        link_desc: str = "",
        link_picurl: str = "",
    ) -> str:
        """创建企业群发消息素材（员工确认后发送给客户）.

        调用成功后，员工会在企微APP「客户联系-待发送」中收到提醒，
        点击确认后消息才会发送给指定的外部联系人（个人微信用户）。

        Args:
            sender: 我方员工的企业微信 UserID
            external_userids: 外部联系人ID列表（个人微信用户）
            text_content: 前置引导文本（可选，纯文本）
            link_title: 链接卡片标题（必填）
            link_url: 链接跳转地址（必填）
            link_desc: 链接卡片描述（纯文本，建议不超过128字）
            link_picurl: 链接卡片封面图URL（可选）

        Returns:
            msgid: 群发素材ID，用于后续追踪发送状态

        Raises:
            RuntimeError: 企微API返回错误时抛出
        """
        url = (
            f"{self.BASE_URL}/externalcontact/add_msg_template"
            f"?access_token={self._get_access_token()}"
        )
        payload: dict = {
            "chat_type": "single",
            "external_userid": external_userids,
            "sender": sender,
        }

        if text_content:
            payload["text"] = {"content": text_content}

        attachments = []
        if link_title and link_url:
            link_payload: dict = {
                "title": link_title,
                "url": link_url,
                "desc": link_desc,
            }
            if link_picurl:
                link_payload["picurl"] = link_picurl
            attachments.append({"msgtype": "link", "link": link_payload})

        if attachments:
            payload["attachments"] = attachments

        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()

        if result.get("errcode") != 0:
            logger.error(
                f"创建群发素材失败: sender={sender}, "
                f"external_userids={external_userids}, err={result}"
            )
            raise RuntimeError(f"创建群发素材失败: {result}")

        msgid = result.get("msgid", "")
        logger.info(
            f"创建群发素材成功: sender={sender}, msgid={msgid}, "
            f"targets={len(external_userids)}"
        )
        return msgid

    # ─────────────────────────────────────────
    # 备选：直接发送（如后续开通免确认权限）
    # ─────────────────────────────────────────
    def send_msg_to_external(
        self,
        follow_user_id: str,
        external_userid: str,
        msg_type: str,
        content: dict,
    ) -> dict:
        """直接发送消息给外部联系人（需要开通客户联系高级权限）.

        Note:
            该接口绕过员工确认，直接发送。是否可用取决于企业微信权限配置。
            每个客户每月最多4条。
        """
        api_url = (
            f"{self.BASE_URL}/externalcontact/message/send"
            f"?access_token={self._get_access_token()}"
        )
        payload = {
            "sender": follow_user_id,
            "msgtype": msg_type,
            msg_type: content,
            "external_userid": [external_userid],
        }
        resp = requests.post(api_url, json=payload, timeout=10)
        result = resp.json()

        if result.get("errcode") != 0:
            logger.error(
                f"企微直接发送失败: follow_user={follow_user_id}, "
                f"external_userid={external_userid}, err={result}"
            )
            raise RuntimeError(f"企微直接发送失败: {result}")

        return result

    # ─────────────────────────────────────────
    # 外部联系人管理
    # ─────────────────────────────────────────
    def get_external_contact(self, external_userid: str) -> dict:
        """获取外部联系人详情."""
        url = (
            f"{self.BASE_URL}/externalcontact/get"
            f"?access_token={self._get_access_token()}"
        )
        resp = requests.get(
            url, params={"external_userid": external_userid}, timeout=10
        )
        return resp.json()

    def get_follow_user_list(self) -> list[str]:
        """获取配置了客户联系功能的成员列表."""
        url = (
            f"{self.BASE_URL}/externalcontact/get_follow_user_list"
            f"?access_token={self._get_access_token()}"
        )
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            return data.get("follow_user", [])
        return []
