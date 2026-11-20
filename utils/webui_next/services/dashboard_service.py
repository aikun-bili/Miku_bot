"""仪表盘服务：聚合插件、黑名单、消息与插件调用统计。"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..formatters import format_duration, now_str, today_key, week_key
from ..paths import CONFIG_FILE, DATA_DIR
from .config_service import load_blacklist
from .plugin_service import get_plugin_list
from .system_service import uptime_seconds, _process_memory_mb


def _load_json(name: str) -> Dict[str, Any]:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _msg_trend(msg_stats: Dict[str, Any], days: int = 30) -> List[Dict[str, Any]]:
    result = []
    today = datetime.now().date()
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(int(s.get("daily", {}).get(day, 0)) for s in msg_stats.values())
        result.append({"date": day, "count": count})
    return result


def _plugin_trend(plugin_stats: Dict[str, Any], days: int = 30) -> List[Dict[str, Any]]:
    result = []
    today = datetime.now().date()
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(int(s.get("__daily__", {}).get(day, 0)) for s in plugin_stats.values())
        result.append({"date": day, "count": count})
    return result


def get_dashboard() -> Dict[str, Any]:
    """返回仪表盘所需的全部统计数据。"""
    plugins = get_plugin_list()
    blacklist = load_blacklist()
    msg_stats = _load_json("message_stats.json")
    plugin_stats = _load_json("plugin_stats.json")

    total_messages = 0
    today_messages = 0
    week_messages = 0
    group_msg_count: Dict[str, int] = {}
    for stats in msg_stats.values():
        total_messages += int(stats.get("total", 0))
        today_messages += int(stats.get("daily", {}).get(today_key(), 0))
        week_messages += int(stats.get("weekly", {}).get(week_key(), 0))
        for gid, count in (stats.get("groups") or {}).items():
            group_msg_count[gid] = group_msg_count.get(gid, 0) + int(count)

    total_plugin_calls = 0
    active_plugins = 0
    for stats in plugin_stats.values():
        calls = int(stats.get("__total__", 0))
        total_plugin_calls += calls
        if calls > 0:
            active_plugins += 1

    group_ranking = sorted(
        ({"group_id": gid, "message_count": cnt} for gid, cnt in group_msg_count.items()),
        key=lambda x: x["message_count"],
        reverse=True,
    )[:20]

    seconds = uptime_seconds()
    process_mb = _process_memory_mb()
    enabled = sum(1 for p in plugins if p["enabled"])

    return {
        "status": "online",
        "uptime": format_duration(seconds).rsplit(" ", 1)[0] if seconds >= 60 else format_duration(seconds),
        "uptime_seconds": seconds,
        "plugin_count": len(plugins),
        "enabled_plugin_count": enabled,
        "disabled_plugin_count": len(plugins) - enabled,
        "global_blacklist_count": len(blacklist["global_disabled"]),
        "group_blacklist_count": len(blacklist["group_disabled"]),
        "user_blacklist_count": len(blacklist["user_disabled"]),
        "memory_usage": f"{process_mb}MB",
        "config_file": str(CONFIG_FILE),
        "last_modified": (
            datetime.fromtimestamp(CONFIG_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            if CONFIG_FILE.exists()
            else "N/A"
        ),
        "total_messages": total_messages,
        "total_users": len(msg_stats),
        "today_messages": today_messages,
        "week_messages": week_messages,
        "total_plugin_calls": total_plugin_calls,
        "active_plugins": active_plugins,
        "group_ranking": group_ranking,
        "msg_trend": _msg_trend(msg_stats),
        "plugin_trend": _plugin_trend(plugin_stats),
        "updated_at": now_str(),
    }


def get_overview() -> Dict[str, Any]:
    """v1 风格的概览数据。"""
    data = get_dashboard()
    return {
        "overview": {
            "status": data["status"],
            "uptime": data["uptime"],
            "plugin_count": data["plugin_count"],
            "enabled_plugin_count": data["enabled_plugin_count"],
            "disabled_plugin_count": data["disabled_plugin_count"],
            "memory_usage": data["memory_usage"],
        },
        "stats": {
            "total_messages": data["total_messages"],
            "total_users": data["total_users"],
            "today_messages": data["today_messages"],
            "total_plugin_calls": data["total_plugin_calls"],
        },
        "system_health": "healthy",
    }
