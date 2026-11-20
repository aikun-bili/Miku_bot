"""认证路由：登录、校验、刷新。"""

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..exceptions import AuthenticationException
from ..responses import ok
from ..services import auth_service


class LoginRequest(BaseModel):
    password: str = Field(default="", description="登录密码")
    token: str = Field(default="", description="兼容旧前端的密码字段")
    username: str = Field(default="", description="用户名（当前不使用）")
    device_name: str = Field(default="", description="仅用于展示的设备名称")


class RefreshRequest(BaseModel):
    refresh_token: str = ""


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return getattr(request.client, "host", "unknown") or "unknown"


router = APIRouter(tags=["auth"])


@router.post("/auth/login", summary="密码登录")
async def login(payload: LoginRequest, request: Request):
    password = payload.password or payload.token
    data = auth_service.login(password, client_ip=client_ip(request))
    return ok(data, "登录成功")


@router.post("/auth", summary="密码登录（旧版兼容）")
async def legacy_login(payload: LoginRequest, request: Request):
    password = payload.password or payload.token
    data = auth_service.login(password, client_ip=client_ip(request))
    return ok(data, "登录成功")


@router.get("/auth/verify", summary="校验 access 令牌")
async def verify(token: str = ""):
    return ok(auth_service.verify(token), "有效")


@router.post("/auth/refresh", summary="刷新令牌")
async def refresh(request: Request, payload: Optional[RefreshRequest] = None):
    refresh_token = ""
    if payload and payload.refresh_token:
        refresh_token = payload.refresh_token
    if not refresh_token:
        refresh_token = (request.query_params.get("refresh_token") or "").strip()
    if not refresh_token:
        try:
            body = await request.json()
            refresh_token = str(body.get("refresh_token", "")).strip()
        except Exception:
            refresh_token = ""
    if not refresh_token:
        raise AuthenticationException("缺少 refresh_token")
    return ok(auth_service.refresh(refresh_token), "刷新成功")
