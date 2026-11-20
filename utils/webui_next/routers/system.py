"""系统路由：状态、健康检查、信息、网络与重启。"""

from fastapi import APIRouter

from ..responses import ok
from ..services import system_service

router = APIRouter(tags=["system"])


@router.get("/system/status", summary="运行状态")
async def system_status():
    return ok(system_service.get_status())


@router.get("/system/health", summary="健康检查")
async def system_health():
    return ok(system_service.get_health())


@router.get("/system/info", summary="系统信息")
async def system_info():
    return ok(system_service.get_info())


@router.get("/system/network", summary="网络信息")
async def system_network():
    return ok(system_service.get_network())


@router.get("/system/ping", summary="连通性检测")
async def system_ping():
    return ok({"pong": True})


@router.post("/system/restart", summary="重启 Bot")
async def system_restart():
    return ok(system_service.restart_bot(), "Bot 正在重启")


@router.post("/restart", summary="重启 Bot（旧版兼容）")
async def restart():
    return ok(system_service.restart_bot(), "Bot 正在重启")
