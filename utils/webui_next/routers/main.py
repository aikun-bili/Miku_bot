"""路由总装：统一注册 API、WebSocket 与页面路由。"""

import asyncio

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from nonebot.log import logger

from ..dependencies import require_auth
from ..exceptions import register_exception_handlers
from ..paths import BASE_DIR
from ..websocket import hub, logs_websocket, status_websocket
from . import auth, config, dashboard, database, file, log, manage, plugin, spa, system

API_PREFIX = "/api"
API_V1_PREFIX = "/miku/api/v1"
LEGACY_API_V1_PREFIX = "/zhenxun/api/v1"
SPA_DIR = BASE_DIR / "admin_web_next"

PROTECTED_ROUTERS = (system, dashboard, plugin, config, file, log, manage, database)

# 旧版页面名：访问时统一跳转到新前端，避免看到已废弃的 UI
HTML_PAGES = {
    "login",
    "dashboard",
    "plugins",
    "plugin",
    "blacklist",
    "config",
    "logs",
    "groups",
    "users",
    "chat",
}
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _register_api_routes(app: FastAPI) -> None:
    # 旧版 MPA：/api/*（页面已由 /next 取代，保留接口兼容）
    app.include_router(auth.router, prefix=API_PREFIX)
    protected = [Depends(require_auth)]
    for module in PROTECTED_ROUTERS:
        app.include_router(module.router, prefix=API_PREFIX, dependencies=protected)

    # 参考前端（/next）：/miku/api/v1/*；旧前缀保留为兼容旧缓存的别名
    for prefix in (API_V1_PREFIX, LEGACY_API_V1_PREFIX):
        app.include_router(spa.auth_router, prefix=prefix)
        app.include_router(spa.router, prefix=prefix)

    # 登录页兼容入口（旧地址）
    app.include_router(auth.router)


def _register_websockets(app: FastAPI) -> None:
    for path in ("/ws/logs", "/miku/ws/v1/logs", "/zhenxun/ws/v1/logs"):
        app.websocket(path)(logs_websocket)
    for path in ("/ws/status", "/miku/ws/v1/status", "/zhenxun/ws/v1/status"):
        app.websocket(path)(status_websocket)


def _register_pages(app: FastAPI) -> None:
    """挂载参考前端（/next）与少量兼容页面。"""

    @app.get("/", include_in_schema=False)
    async def index():
        return RedirectResponse("/next/")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        path = SPA_DIR / "favicon.ico"
        if not path.exists():
            raise HTTPException(status_code=404, detail="图标不存在")
        return FileResponse(path)

    @app.get("/next", include_in_schema=False)
    async def next_root():
        return RedirectResponse("/next/")

    @app.get("/next/{spa_path:path}", include_in_schema=False)
    async def next_page(spa_path: str):
        if ".." in spa_path or "\\" in spa_path:
            raise HTTPException(status_code=404, detail="页面不存在")

        target = SPA_DIR / spa_path if spa_path else SPA_DIR / "index.html"
        if spa_path and target.is_file():
            return FileResponse(target, headers=NO_CACHE_HEADERS)

        index_file = SPA_DIR / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="前端资源缺失")
        return HTMLResponse(index_file.read_text(encoding="utf-8"), headers=NO_CACHE_HEADERS)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def page_route(full_path: str):
        if not full_path or ".." in full_path or "\\" in full_path:
            raise HTTPException(status_code=404, detail="页面不存在")

        # 旧版页面统一跳转到新前端，避免继续看到废弃 UI
        if full_path in HTML_PAGES:
            return RedirectResponse("/next/" if full_path == "login" else f"/next/{full_path}")

        raise HTTPException(status_code=404, detail="页面不存在")


def _startup_tasks() -> None:
    try:
        hub.bind_loop(asyncio.get_running_loop())
    except RuntimeError:
        pass
    hub.install()

    try:
        from utils.ai_model_config import LEGACY_AI_CONFIG_MIGRATED

        if LEGACY_AI_CONFIG_MIGRATED:
            from ..services.config_service import reload_config_manager

            reload_config_manager()
    except Exception:
        pass


def run_startup_tasks() -> None:
    """ASGI 启动后执行：绑定事件循环、安装日志 hub 等。"""
    _startup_tasks()


def mount(app: FastAPI, startup: bool = True) -> None:
    """把 WebUI 挂载到给定的 FastAPI 应用上。

    ``startup=False`` 用于在 ``nonebot.run()`` 之前挂载：异常处理器必须在
    Starlette 构建中间件栈之前注册，否则启动回调里注册的处理器不会生效，
    业务异常会被当成未捕获异常并以 500 返回。
    """
    register_exception_handlers(app)

    _register_api_routes(app)
    _register_websockets(app)
    _register_pages(app)

    if startup:
        _startup_tasks()
    try:
        from ..services.system_service import get_network

        network = get_network()
        logger.success(
            f"[WebUI] 管理后台已挂载：http://{network['host']}:{network['port']}/ "
            f"（JWT 鉴权，日志/状态 WebSocket 已就绪）"
        )
    except Exception:
        logger.success("[WebUI] 管理后台已挂载（JWT 鉴权，WebSocket 已就绪）")
