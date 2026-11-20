"""仪表盘路由。"""

from fastapi import APIRouter

from ..responses import ok
from ..services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", summary="仪表盘数据")
async def dashboard():
    return ok(dashboard_service.get_dashboard())


@router.get("/dashboard/overview", summary="仪表盘概览")
async def dashboard_overview():
    return ok(dashboard_service.get_overview())
