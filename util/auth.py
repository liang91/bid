"""JWT 认证工具.

提供 Token 生成、解码以及 FastAPI 依赖注入功能。
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

class Auth:
    secret = "bid-service-2026"

    @classmethod
    def gen_token(cls, user_id: int, platform: str) -> str:
        """生成 JWT access token.
            Args:
                user_id: 用户主键 ID
                platform: 终端平台
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),  # JWT 标准声明：主题
            "user_id": user_id,  # 业务字段
            "platform": platform,  # 终端平台
            "iat": int(now.timestamp()),  # 签发时间戳
        }
        return jwt.encode(payload, key=cls.secret, algorithm='HS256')

    @classmethod
    def decode_token(cls, token: str) -> Optional[dict]:
        """解码并验证 JWT token.
        Args:
            token: JWT 字符串
        Returns:
            解码后的 payload 字典；验证失败返回 None
        """
        try:
            payload = jwt.decode(token, key=cls.secret, algorithms=['HS256'])
            return payload
        except JWTError:
            return None

    @classmethod
    def user(cls, request: Request) -> dict:
        """FastAPI 依赖：从请求头 token 字段中提取并验证用户信息.

        前端在 Header 中直接传 token，例如：
            token: eyJhbGciOiJIUzI1NiIs...

        在需要登录保护的接口中使用：
            @router.get("/profile")
            def profile(current_user: dict = Depends(Auth.get_current_user)):
                return {"user_id": current_user["user_id"]}

        Returns:
            dict: {"user_id": int, "platform": str}

        Raises:
            HTTPException(401): 缺少 token 或 token 无效/过期
        """
        token = request.headers.get("token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少认证凭证",
            )

        payload = cls.decode_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证",
            )

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证",
            )

        return {"user_id": user_id, "platform": payload.get("platform", '')}

