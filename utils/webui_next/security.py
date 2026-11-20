"""JWT 签发与校验（HS256，无第三方依赖）。

- ``access`` 令牌默认 30 分钟，携带 ``exp``。
- ``refresh`` 令牌默认 7 天，只能用于换取新的 access 令牌。
- 密钥优先读取环境变量 ``WEBUI_JWT_SECRET``，否则由 WebUI 密码派生，
  保证重启后旧令牌仍可校验。
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

from .exceptions import AuthenticationException

ACCESS_EXPIRES_SECONDS = 30 * 60
REFRESH_EXPIRES_SECONDS = 7 * 24 * 3600
_ALGORITHM = "HS256"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _secret() -> bytes:
    env_secret = os.environ.get("WEBUI_JWT_SECRET", "").strip()
    if env_secret:
        return env_secret.encode("utf-8")
    from .services.auth_service import get_password

    return hmac.new(
        get_password().encode("utf-8"), b"mikubot-webui-jwt", hashlib.sha256
    ).digest()


def _sign(signing_input: bytes) -> str:
    signature = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
    return _b64encode(signature)


def create_token(
    subject: str = "admin",
    token_type: str = "access",
    expires_in: Optional[int] = None,
) -> Dict[str, Any]:
    """签发 JWT，返回 ``{"token": str, "expires_in": int, "exp": int}``。"""
    if expires_in is None:
        expires_in = ACCESS_EXPIRES_SECONDS if token_type == "access" else REFRESH_EXPIRES_SECONDS
    issued_at = int(time.time())
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + expires_in,
        "jti": secrets.token_hex(8),
    }
    header = {"alg": _ALGORITHM, "typ": "JWT"}
    header_part = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    return {
        "token": f"{header_part}.{payload_part}.{_sign(signing_input)}",
        "expires_in": expires_in,
        "exp": payload["exp"],
        "token_type": token_type,
    }


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """校验 JWT 并返回 payload，失败抛 ``AuthenticationException``。"""
    try:
        header_part, payload_part, signature = token.split(".")
    except ValueError as e:
        raise AuthenticationException("Token 格式错误") from e

    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    if not hmac.compare_digest(signature, _sign(signing_input)):
        raise AuthenticationException("Token 签名无效")

    try:
        payload = json.loads(_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError) as e:
        raise AuthenticationException("Token 内容无效") from e

    if payload.get("type") != expected_type:
        raise AuthenticationException("Token 类型错误")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise AuthenticationException("登录已过期，请重新登录")
    return payload


def fake_device_token() -> str:
    """生成仅用于界面展示的伪设备令牌，不参与任何真实校验。"""
    return f"miku_{secrets.token_hex(8)}"


def mask_token(token: str) -> str:
    if len(token) <= 12:
        return token
    return f"{token[:8]}...{token[-4:]}"
