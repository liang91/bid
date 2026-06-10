"""微信小程序服务端 API 封装.
参考文档: https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html
"""

import requests
from loguru import logger
from config import config


class WeChat:
    login_url = "https://api.weixin.qq.com/sns/jscode2session"

    @classmethod
    def login(cls, js_code: str) -> dict:
        """用小程序登录 code 换取 openid 和 session_key.
        Args:
            js_code: 前端 wx.login() 获取的临时登录凭证
        Returns:
            dict: 包含 openid, session_key, unionid（如有）等字段；
                  失败时包含 errcode 和 errmsg
        """
        appid = config.get("wx_mini.appid", "")
        secret = config.get("wx_mini.secret", "")

        if not appid or not secret:
            logger.error("[微信] 缺少小程序 appid 或 secret 配置")
            return {"errcode": -1, "errmsg": "服务器配置缺失"}

        params = {
            "appid": appid,
            "secret": secret,
            "js_code": js_code,
            "grant_type": "authorization_code",
        }

        try:
            resp = requests.get(cls.login_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"[微信] 请求 jscode2session 失败: {e}")
            return {"errcode": -1, "errmsg": f"网络请求失败: {e}"}

        if "errcode" in data and data["errcode"] != 0:
            logger.warning(f"[微信] jscode2session 返回错误: {data}")

        logger.info(f"[微信] code2session 成功, openid={data.get('openid', '')[:8]}...")
        return data
