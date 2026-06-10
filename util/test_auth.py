"""JWT 认证工具测试."""

import pytest
from datetime import datetime, timezone
from fastapi import HTTPException, status
from unittest.mock import MagicMock

from util.auth import Auth


class TestJWTToken:
    """测试 Token 生成与解码."""

    def test_create_and_decode_token(self):
        token = Auth.gen_token(user_id=42, platform="mini")
        assert isinstance(token, str)

        payload = Auth.decode_token(token)
        assert payload is not None
        assert payload["user_id"] == 42
        assert payload["platform"] == "mini"
        assert payload["sub"] == "42"

    def test_decode_invalid_token(self):
        assert Auth.decode_token("not.a.token") is None
        assert Auth.decode_token("") is None

    def test_token_iat(self):
        before = int(datetime.now(timezone.utc).timestamp())
        token = Auth.gen_token(user_id=1, platform="mini")
        after = int(datetime.now(timezone.utc).timestamp())

        payload = Auth.decode_token(token)
        assert payload is not None
        assert before <= payload["iat"] <= after


class TestGetCurrentUser:
    """测试 FastAPI 依赖 get_current_user."""

    def _make_request(self, token: str | None = None):
        """构造一个 mock Request，模拟 header 中的 token 字段."""
        request = MagicMock()
        request.headers = {}
        if token:
            request.headers["token"] = token
        return request

    def test_valid_token(self):
        token = Auth.gen_token(user_id=42, platform="mini")
        request = self._make_request(token)
        user = Auth.user(request)
        assert user["user_id"] == 42
        assert user["platform"] == "mini"

    def test_missing_token(self):
        request = self._make_request()
        with pytest.raises(HTTPException) as exc_info:
            Auth.user(request)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "缺少认证凭证" in exc_info.value.detail

    def test_invalid_token(self):
        request = self._make_request("bad-token")
        with pytest.raises(HTTPException) as exc_info:
            Auth.user(request)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "无效" in exc_info.value.detail

