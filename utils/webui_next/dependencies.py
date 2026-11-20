"""依赖注入：统一的 JWT 鉴权依赖。"""

from typing import Any, Dict

from fastapi import Request

from .exceptions import AuthenticationException
from .security import decode_token
from .services.auth_service import check_password


async def get_current_user(request: Request) -> Dict[str, Any]:
    """校验访问令牌。

    同时兼容两种请求头：
    - ``Authorization: Bearer <jwt>``（本项目的旧前端 / API 文档）
    - ``Authorization: <jwt>``（参考前端直接写入 token）

    以及旧版「密码本身作为令牌」的请求。
    """
    raw = (request.headers.get("authorization") or "").strip()
    token = raw[7:].strip() if raw.lower().startswith("bearer ") else raw
    if not token:
        token = (request.query_params.get("token") or "").strip()

    if not token:
        raise AuthenticationException("缺少登录令牌")

    if check_password(token):
        return {"username": "admin", "legacy": True}

    payload = decode_token(token, expected_type="access")
    return {"username": payload.get("sub", "admin"), "payload": payload}


require_auth = get_current_user
