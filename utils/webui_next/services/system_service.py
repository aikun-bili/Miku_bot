"""系统服务：运行状态、健康评估、重启与网络信息。"""

import os
import socket
import sys
import time
from typing import Any, Dict

from nonebot.log import logger

from ..formatters import format_duration, now_str
from ..paths import BASE_DIR, CONFIG_FILE

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover
    psutil = None
    _HAS_PSUTIL = False

START_TIME = time.time()


def uptime_seconds() -> int:
    return int(time.time() - START_TIME)


def _process_memory_mb() -> float:
    if not _HAS_PSUTIL:
        return 0.0
    try:
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return 0.0


def get_status() -> Dict[str, Any]:
    """CPU / 内存 / 磁盘 / 运行时长。"""
    cpu = memory = disk = 0.0
    memory_total_mb = 0.0
    if _HAS_PSUTIL:
        try:
            cpu = psutil.cpu_percent(interval=0.1)
        except Exception:
            pass
        try:
            mem = psutil.virtual_memory()
            memory = mem.percent
            memory_total_mb = round(mem.total / 1024 / 1024, 1)
        except Exception:
            pass
        try:
            disk = psutil.disk_usage(str(BASE_DIR)).percent
        except Exception:
            pass

    seconds = uptime_seconds()
    process_mb = _process_memory_mb()
    return {
        "status": "online",
        "uptime": seconds,
        "uptime_formatted": format_duration(seconds),
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "memory_usage_mb": process_mb,
        "memory_total_mb": memory_total_mb,
        "memory_usage": f"{process_mb}MB",
        "server_time": now_str(),
    }


def get_health() -> Dict[str, Any]:
    """根据资源占用给出健康度。"""
    status = get_status()
    level = "healthy"
    if status["cpu"] >= 90 or status["memory"] >= 90 or status["disk"] >= 90:
        level = "error"
    elif status["cpu"] >= 75 or status["memory"] >= 75 or status["disk"] >= 80:
        level = "warning"
    return {
        "status": level,
        "cpu_usage": status["cpu"],
        "memory_usage": status["memory"],
        "disk_usage": status["disk"],
        "uptime": status["uptime"],
        "checked_at": now_str(),
    }


def get_info() -> Dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "pid": os.getpid(),
        "base_dir": str(BASE_DIR),
        "config_file": str(CONFIG_FILE),
        "config_exists": CONFIG_FILE.exists(),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(START_TIME)),
    }


def get_network() -> Dict[str, Any]:
    """返回监听配置与本机 IP 列表（不发起外网请求）。"""
    host = "127.0.0.1"
    port = 3108
    try:
        from .config_service import load_yaml

        bot_conf = load_yaml().get("bot", {})
        if isinstance(bot_conf, dict):
            host = str(bot_conf.get("host", host))
            port = int(bot_conf.get("port", port))
    except Exception:
        pass

    addresses = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addr = info[4][0]
            if addr not in addresses:
                addresses.append(addr)
    except OSError:
        pass
    return {"host": host, "port": port, "addresses": addresses}


def restart_bot() -> Dict[str, Any]:
    """延迟 1 秒后用当前解释器重启 bot.py。"""
    import asyncio

    logger.warning("[WebUI] 收到重启指令，Bot 即将重启...")
    loop = asyncio.get_event_loop()
    python = sys.executable
    bot_entry = str(BASE_DIR / "bot.py")
    loop.call_later(1, lambda: os.execv(python, [python, bot_entry]))
    return {"restarting": True, "message": "Bot 正在重启，请稍后刷新页面"}
