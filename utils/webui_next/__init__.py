"""MikuBot WebUI Next —— 模块化后台。

对外只暴露 :func:`mount`，由 ``utils/webui.py`` 作为薄入口调用。
"""

from typing import Optional

from nonebot import get_driver
from nonebot.log import logger

from .routers.main import mount as mount_routes
from .routers.main import run_startup_tasks


def get_app():
    """获取 NoneBot 使用的 FastAPI 应用实例。"""
    try:
        import nonebot

        app = nonebot.get_app()
    except Exception:
        driver = get_driver()
        app = (
            getattr(driver, "server_app", None)
            or getattr(driver, "asgi", None)
            or getattr(driver, "_server_app", None)
            or getattr(driver, "_server", None)
        )
    return app


def mount(app: Optional[object] = None, startup: bool = True) -> bool:
    """挂载 WebUI，返回是否成功。"""
    try:
        from fastapi import FastAPI
    except ImportError:
        logger.warning("[WebUI] FastAPI 未安装，管理后台不可用")
        return False

    target = app or get_app()
    if target is None or not isinstance(target, FastAPI):
        logger.warning(
            f"[WebUI] 无法获取 FastAPI 应用（类型: {type(target).__name__}），管理后台未挂载"
        )
        return False

    mount_routes(target, startup=startup)
    return True


__all__ = ["mount", "get_app", "run_startup_tasks"]
