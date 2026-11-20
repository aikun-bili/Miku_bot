"""格式化工具：文件大小、时间、运行时长等。"""

from datetime import datetime
from typing import Union


def format_size(size: Union[int, float]) -> str:
    """把字节数格式化为可读字符串。"""
    try:
        size = float(size)
    except (TypeError, ValueError):
        return "0B"
    if size < 1024:
        return f"{int(size)}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    return f"{size / 1024 / 1024 / 1024:.2f}GB"


def format_duration(seconds: Union[int, float]) -> str:
    """把秒数格式化为 ``1h 2m 3s``。"""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_timestamp(ts: Union[int, float, None], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """把时间戳格式化为本地时间字符串。"""
    if not ts:
        return "N/A"
    try:
        return datetime.fromtimestamp(float(ts)).strftime(fmt)
    except (TypeError, ValueError, OSError):
        return "N/A"


def format_percent(value: Union[int, float, None]) -> str:
    if value is None:
        return "0%"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0%"


def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def week_key() -> str:
    return datetime.now().strftime("%Y-W%W")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_datetime(value: str) -> datetime:
    """解析 ``YYYY-MM-DD HH:MM:SS``，失败时返回当前时间。"""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return datetime.now()
