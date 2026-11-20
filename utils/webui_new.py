"""MikuBot WebUI 新入口（薄入口）。

职责仅有两件事：
1. 把 ``utils.webui_next`` 挂载到 NoneBot 的 FastAPI 应用；
2. 保持 TCP 监听健康检查与异常自恢复。

前端为 ``admin_web_next/``（参考 Vue + Element Plus 后台架构重制的管理界面），
访问 ``/next/`` 即可打开。
"""

import os
import socket
import sys
import threading
import time
from typing import Optional

from nonebot import get_driver
from nonebot.log import logger

from utils.webui_next import mount as _mount_webui
from utils.webui_next import run_startup_tasks
from utils.webui_next.paths import BASE_DIR

_LISTENER_CHECK_INTERVAL = 30
_LISTENER_CHECK_TIMEOUT = 5
_LISTENER_FAILURE_ALERT_EVERY = 5
_LISTENER_FAILURE_RESTART_AFTER = 3
_LISTENER_RESTART_COOLDOWN_SECONDS = 600
_LISTENER_RESTART_ENV = "MIKU_WEBUI_WATCHDOG_RESTART_AT"

_listener_check_stop = threading.Event()
_listener_check_thread: Optional[threading.Thread] = None


def _mount_admin() -> bool:
    """立即挂载 WebUI 路由与异常处理器。

    必须在 ``nonebot.run()`` 之前执行：Starlette 在首次 ASGI 调用（含 lifespan）
    时构建中间件栈，之后注册的异常处理器不会生效，业务异常会被当成未捕获
    异常并以 500 返回。
    """
    return _mount_webui(startup=False)


def _webui_startup() -> None:
    """ASGI 启动回调：绑定事件循环、安装日志 hub、启动监听健康检查。"""
    run_startup_tasks()
    _start_listener_healthcheck()


def _check_listener(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=_LISTENER_CHECK_TIMEOUT):
        pass


def _restart_bot_for_listener_failure(
    host: str, port: int, failures: int, outage_seconds: int, error: OSError
) -> None:
    now = int(time.time())
    previous_restart = os.environ.get(_LISTENER_RESTART_ENV)
    if previous_restart:
        try:
            restart_age = now - int(previous_restart)
        except ValueError:
            logger.warning(f"[WebUI] 忽略无效的自动恢复冷却标记: {previous_restart!r}")
        else:
            if 0 <= restart_age < _LISTENER_RESTART_COOLDOWN_SECONDS:
                logger.critical(
                    f"[WebUI] 监听仍不可用 ({host}:{port})，且 Bot 在 {restart_age} 秒前"
                    "已尝试自动恢复；为避免重启循环，本次不再自动重启。请检查端口占用和启动日志。"
                )
                return

    logger.critical(
        f"[WebUI] TCP 监听连续失败 {failures} 次、持续 {outage_seconds} 秒，"
        f"将自动重启 Bot 恢复 WebUI；目标={host}:{port}，"
        f"错误={type(error).__name__}: {error}，PID={os.getpid()}"
    )
    os.environ[_LISTENER_RESTART_ENV] = str(now)
    python = sys.executable
    os.execv(python, [python, str(BASE_DIR / "bot.py")])


def _start_listener_healthcheck() -> None:
    global _listener_check_thread

    if _listener_check_thread and _listener_check_thread.is_alive():
        return

    driver = get_driver()
    host = str(getattr(driver.config, "host", "127.0.0.1"))
    port = int(getattr(driver.config, "port", 3108))
    if host == "0.0.0.0":
        check_host = "127.0.0.1"
    elif host == "::":
        check_host = "::1"
    else:
        check_host = host
    _listener_check_stop.clear()

    def _monitor() -> None:
        failures = 0
        outage_started = None
        recovery_decided = False
        while not _listener_check_stop.wait(_LISTENER_CHECK_INTERVAL):
            try:
                _check_listener(check_host, port)
            except OSError as e:
                failures += 1
                if outage_started is None:
                    outage_started = time.monotonic()
                    logger.warning(
                        f"[WebUI] TCP 监听健康检查失败 ({check_host}:{port}): "
                        f"{type(e).__name__}: {e}"
                    )
                elif failures == 3 or failures % _LISTENER_FAILURE_ALERT_EVERY == 0:
                    elapsed = int(time.monotonic() - outage_started)
                    logger.error(
                        f"[WebUI] TCP 监听连续失败 {failures} 次，已持续 {elapsed} 秒；"
                        f"Bot PID={os.getpid()}，目标={check_host}:{port}，"
                        f"最近错误={type(e).__name__}: {e}"
                    )
                if not recovery_decided and failures >= _LISTENER_FAILURE_RESTART_AFTER:
                    recovery_decided = True
                    try:
                        _restart_bot_for_listener_failure(
                            check_host, port, failures, int(time.monotonic() - outage_started), e
                        )
                    except OSError:
                        logger.exception(
                            "[WebUI] 自动重启 Bot 失败；监听仍不可用，请人工检查进程和端口状态"
                        )
            else:
                if failures:
                    elapsed = int(time.monotonic() - outage_started)
                    logger.success(
                        f"[WebUI] TCP 监听已恢复 ({check_host}:{port})，"
                        f"中断约 {elapsed} 秒，连续失败 {failures} 次"
                    )
                    failures = 0
                    outage_started = None
                    recovery_decided = False
                if os.environ.pop(_LISTENER_RESTART_ENV, None) is not None:
                    logger.info("[WebUI] 自动恢复后的监听探测成功，已清除重启冷却标记")

    _listener_check_thread = threading.Thread(
        target=_monitor, name="webui-listener-healthcheck", daemon=True
    )
    _listener_check_thread.start()
    logger.info(
        f"[WebUI] TCP 监听健康检查已启动：{check_host}:{port}，间隔 {_LISTENER_CHECK_INTERVAL} 秒"
    )


def _stop_listener_healthcheck() -> None:
    _listener_check_stop.set()
    logger.warning("[WebUI] 收到 ASGI 关闭生命周期回调，已停止监听健康检查")


def _register_hook() -> None:
    try:
        # 先立即挂载（异常处理器要赶在中间件栈构建前注册）
        mounted = _mount_admin()
        driver = get_driver()
        if hasattr(driver, "on_startup") and callable(driver.on_startup):
            if not mounted:
                driver.on_startup(_mount_admin)
            driver.on_startup(_webui_startup)
            if hasattr(driver, "on_shutdown") and callable(driver.on_shutdown):
                driver.on_shutdown(_stop_listener_healthcheck)
        else:  # pragma: no cover - 非标准驱动
            _webui_startup()
    except Exception as e:
        logger.warning(f"[WebUI] 注册启动钩子失败: {e}")


_register_hook()
