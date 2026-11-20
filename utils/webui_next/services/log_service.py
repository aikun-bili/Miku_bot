"""日志服务：日志文件列表、读取与尾部截取。"""

from datetime import datetime
from typing import Any, Dict, List

from ..exceptions import FileException
from ..formatters import format_size
from ..paths import LOGS_DIR

MAX_LOG_LINES = 500


def list_log_files() -> List[Dict[str, Any]]:
    if not LOGS_DIR.exists():
        return []
    files = []
    for path in sorted(LOGS_DIR.glob("bot_*.log"), reverse=True):
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "name": path.name,
                "date": path.stem.replace("bot_", ""),
                "size": stat.st_size,
                "size_str": format_size(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            }
        )
    return files


def _resolve(filename: str):
    if not filename.startswith("bot_") or not filename.endswith(".log"):
        raise FileException("不允许访问此文件")
    path = LOGS_DIR / filename
    if not path.exists():
        raise FileException("日志文件不存在")
    return path


def read_log_file(filename: str, max_lines: int = MAX_LOG_LINES) -> Dict[str, Any]:
    path = _resolve(filename)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise FileException(f"读取日志失败: {e}") from e

    lines = content.splitlines()
    total = len(lines)
    max_lines = max(1, int(max_lines))
    recent = lines[-max_lines:]
    stat = path.stat()
    return {
        "filename": filename,
        "lines": recent,
        "total": total,
        "has_more": total > len(recent),
        "size_bytes": stat.st_size,
        "size_str": format_size(stat.st_size),
    }


def tail_log_file(filename: str, lines: int = 100) -> Dict[str, Any]:
    return read_log_file(filename, max(1, int(lines)))
