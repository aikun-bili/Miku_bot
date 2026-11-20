"""认证服务：密码校验 + JWT 签发 / 刷新。"""

import time
from typing import Any, Dict

from ..exceptions import AuthenticationException
from ..formatters import now_str
from ..paths import BASE_DIR
from ..security import (
    ACCESS_EXPIRES_SECONDS,
    REFRESH_EXPIRES_SECONDS,
    create_token,
    decode_token,
    fake_device_token,
)


def get_password() -> str:
    """读取 WebUI 登录密码。

    优先级：1) ``.env`` 的 ``WEBUI_PASSWORD``  2) ``bot.yaml`` 的 ``bot.webui_password``
    3) 默认值 ``miku8888``。
    """
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("WEBUI_PASSWORD="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except OSError:
            pass

    try:
        from .config_service import load_yaml

        bot_conf = load_yaml().get("bot", {})
        if isinstance(bot_conf, dict):
            value = bot_conf.get("webui_password", "")
            if isinstance(value, str) and value.strip():
                return value.strip()
    except Exception:
        pass
    return "miku8888"


def check_password(token: str) -> bool:
    """判断给定字符串是否等于登录密码（兼容旧版令牌）。"""
    return bool(token) and token == get_password()


def _token_payload() -> Dict[str, Any]:
    access = create_token("admin", "access", ACCESS_EXPIRES_SECONDS)
    refresh = create_token("admin", "refresh", REFRESH_EXPIRES_SECONDS)
    return {
        "access_token": access["token"],
        "refresh_token": refresh["token"],
        "token_type": "bearer",
        "expires_in": access["expires_in"],
        "expires_at": access["exp"],
        "refresh_expires_in": refresh["expires_in"],
        # 仅用于界面展示：不参与任何真实设备校验
        "device_token": fake_device_token(),
        "miku_token": fake_device_token(),
        "username": "admin",
        "is_admin": True,
        "login_at": now_str(),
        "server_time": int(time.time()),
    }


def login(password: str, client_ip: str = "unknown") -> Dict[str, Any]:
    """密码登录，成功返回令牌信息。"""
    if not check_password((password or "").strip()):
        raise AuthenticationException("密码错误")

    from nonebot.log import logger

    logger.success(f"[WebUI] 登录成功（{client_ip}）")
    payload = _token_payload()
    payload["ip"] = client_ip
    return payload


def refresh(token: str) -> Dict[str, Any]:
    """用 refresh 令牌换取新的 access / refresh 令牌。"""
    if not token:
        raise AuthenticationException("缺少 refresh_token")
    decode_token(token, expected_type="refresh")
    return _token_payload()


def refresh_compat(token: str) -> Dict[str, Any]:
    """兼容参考前端：refresh 接口允许传入 access 或 refresh 令牌。"""
    try:
        return refresh(token)
    except AuthenticationException:
        verify(token)
        return _token_payload()


def verify(access_token: str) -> Dict[str, Any]:
    """校验 access 令牌。"""
    if not access_token:
        raise AuthenticationException("缺少 token")
    if check_password(access_token):
        return {"valid": True, "username": "admin", "legacy": True}
    payload = decode_token(access_token, expected_type="access")
    return {
        "valid": True,
        "username": payload.get("sub", "admin"),
        "exp": payload.get("exp"),
        "expires_in": max(0, int(payload.get("exp", 0)) - int(time.time())),
    }


def read_env_keys() -> Dict[str, str]:
    """读取 .env 中的键值（用于配置页展示，隐藏敏感值由前端处理）。"""
    result: Dict[str, str] = {}
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return result
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return result
