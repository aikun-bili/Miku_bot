"""SPA 数据服务：为参考前端（/next）提供真实数据。

数据来源保持 miku_bot 原有结构：
- ``data/message_stats.json`` 消息统计
- ``data/plugin_stats.json`` 插件调用统计
- ``data/users/*.json`` 用户金币 / 好感度
- ``data/miku.db`` 金币、群组、商店等
- NoneBot Bot 实时群组 / 好友信息
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import nonebot
from nonebot.log import logger

from ..formatters import format_duration
from ..paths import DATA_DIR
from . import plugin_service, system_service

USER_DIR = DATA_DIR / "users"
GROUP_SETTINGS_FILE = DATA_DIR / "group_settings.json"
REQUEST_FILE = DATA_DIR / "friend_requests.json"

GITHUB_REPO = "aikun-bili/Miku_bot"
_COMMITS_TTL = 600
_commits_cache: Dict[str, Any] = {"ts": 0.0, "data": []}

_cache: Dict[str, Any] = {}


def _cached(key: str, ttl: float, factory):
    item = _cache.get(key)
    now = time.time()
    if item and now - item[0] < ttl:
        return item[1]
    value = factory()
    _cache[key] = (now, value)
    return value


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def first_bot():
    try:
        bots = nonebot.get_bots()
    except Exception:
        return None
    if not bots:
        return None
    return next(iter(bots.values()))


def bot_count() -> int:
    try:
        return len(nonebot.get_bots())
    except Exception:
        return 0


# ==================== 用户数据 ====================
def load_user(user_id: str) -> Dict[str, Any]:
    data = _load_json(USER_DIR / f"{user_id}.json")
    return data if isinstance(data, dict) else {}


def save_user(user_id: str, data: Dict[str, Any]) -> None:
    _save_json(USER_DIR / f"{user_id}.json", data)
    _cache.pop("users", None)


def iter_users() -> List[Dict[str, Any]]:
    if not USER_DIR.exists():
        return []

    def _read():
        users = []
        for path in USER_DIR.glob("*.json"):
            data = _load_json(path)
            if isinstance(data, dict):
                data.setdefault("user_id", path.stem)
                users.append(data)
        return users

    return _cached("users", 30, _read)


def user_avatar(user_id: str) -> str:
    return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100"


# ==================== 消息 / 插件统计 ====================
def message_stats() -> Dict[str, Any]:
    data = _load_json(DATA_DIR / "message_stats.json")
    return data if isinstance(data, dict) else {}


def plugin_stats() -> Dict[str, Any]:
    data = _load_json(DATA_DIR / "plugin_stats.json")
    return data if isinstance(data, dict) else {}


def total_messages() -> int:
    return sum(int(v.get("total", 0)) for v in message_stats().values())


def today_messages() -> int:
    day = datetime.now().strftime("%Y-%m-%d")
    return sum(int(v.get("daily", {}).get(day, 0)) for v in message_stats().values())


def active_users_today() -> int:
    day = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for v in message_stats().values() if int(v.get("daily", {}).get(day, 0)) > 0)


def group_message_counts(days: int = 7) -> Dict[str, int]:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    result: Dict[str, int] = {}
    for stats in message_stats().values():
        daily = stats.get("daily", {})
        if not isinstance(daily, dict):
            continue
        for day, value in daily.items():
            if day < since:
                continue
            for gid, count in (stats.get("groups") or {}).items():
                # 用户维度无法精确拆分到某天，按占比估算
                total = int(stats.get("total", 0)) or 1
                result[gid] = result.get(gid, 0) + int(int(value) * int(count) / total)
    return result


def total_plugin_calls() -> int:
    return sum(int(v.get("__total__", 0)) for v in plugin_stats().values())


def today_plugin_calls() -> int:
    day = datetime.now().strftime("%Y-%m-%d")
    return sum(int(v.get("__daily__", {}).get(day, 0)) for v in plugin_stats().values())


def chat_statistics() -> Dict[str, int]:
    now = datetime.now()
    total = 0
    day = week = month = year = 0
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    year_start = now - timedelta(days=365)
    for stats in message_stats().values():
        total += int(stats.get("total", 0))
        daily = stats.get("daily", {}) if isinstance(stats.get("daily"), dict) else {}
        for key, value in daily.items():
            try:
                date = datetime.strptime(key, "%Y-%m-%d")
            except ValueError:
                continue
            value = int(value)
            if date.date() == now.date():
                day += value
            if date >= week_start:
                week += value
            if date >= month_start:
                month += value
            if date >= year_start:
                year += value
    return {"all": total, "day": day, "week": week, "month": month, "year": year}


def plugin_call_statistics() -> Dict[str, int]:
    now = datetime.now()
    total = day = week = month = year = 0
    for stats in plugin_stats().values():
        total += int(stats.get("__total__", 0))
        daily = stats.get("__daily__", {})
        if not isinstance(daily, dict):
            continue
        for key, value in daily.items():
            try:
                date = datetime.strptime(key, "%Y-%m-%d")
            except ValueError:
                continue
            value = int(value)
            if date.date() == now.date():
                day += value
            if date >= now - timedelta(days=7):
                week += value
            if date >= now - timedelta(days=30):
                month += value
            if date >= now - timedelta(days=365):
                year += value
    return {"all": total, "day": day, "week": week, "month": month, "year": year}


# ==================== Bot / 群 / 好友 ====================
async def _group_list(bot) -> List[Dict[str, Any]]:
    try:
        return await bot.get_group_list()
    except Exception:
        return []


async def _friend_list(bot) -> List[Dict[str, Any]]:
    try:
        return await bot.get_friend_list()
    except Exception:
        return []


async def group_list(bot_id: Optional[str] = None) -> List[Dict[str, Any]]:
    bot = first_bot()
    if bot is None:
        return []
    groups = await _group_list(bot)
    return [
        {
            "group_id": str(g.get("group_id", "")),
            "group_name": g.get("group_name", "") or str(g.get("group_id", "")),
            "ava_url": f"https://p.qlogo.cn/gh/{g.get('group_id')}/{g.get('group_id')}/100",
        }
        for g in groups
    ]


async def friend_list(bot_id: Optional[str] = None) -> List[Dict[str, Any]]:
    bot = first_bot()
    if bot is None:
        return []
    friends = await _friend_list(bot)
    return [
        {
            "user_id": str(f.get("user_id", "")),
            "nickname": f.get("remark") or f.get("nickname") or str(f.get("user_id", "")),
            "ava_url": user_avatar(str(f.get("user_id", ""))),
        }
        for f in friends
    ]


async def _counts() -> Dict[str, int]:
    bot = first_bot()
    if bot is None:
        return {"groups": 0, "friends": 0}
    groups, friends = await asyncio.gather(_group_list(bot), _friend_list(bot))
    return {"groups": len(groups), "friends": len(friends)}


async def bot_status(bot_id: Optional[str] = None) -> Dict[str, Any]:
    bot = first_bot()
    seconds = system_service.uptime_seconds()
    if bot is None:
        return {
            "self_id": None,
            "nickname": None,
            "ava_url": None,
            "is_running": False,
            "uptime": seconds,
            "uptime_formatted": format_duration(seconds),
            "group_count": 0,
            "friend_count": 0,
            "message_count": total_messages(),
            "start_time": datetime.now().isoformat(),
        }

    nickname = getattr(bot, "self_id", "")
    try:
        login = await bot.get_login_info()
        nickname = login.get("nickname", nickname)
    except Exception:
        pass
    counts = await _counts()
    return {
        "self_id": str(getattr(bot, "self_id", "")),
        "nickname": nickname,
        "ava_url": f"https://q1.qlogo.cn/g?b=qq&nk={getattr(bot, 'self_id', '')}&s=640",
        "is_running": True,
        "uptime": seconds,
        "uptime_formatted": format_duration(seconds),
        "group_count": counts["groups"],
        "friend_count": counts["friends"],
        "message_count": total_messages(),
        "start_time": datetime.fromtimestamp(
            time.time() - seconds
        ).isoformat(),
    }


async def bot_status_list(bot_id: Optional[str] = None) -> Dict[str, Any]:
    current = await bot_status(bot_id)
    bots = [current] if current.get("is_running") else []
    return {"current": current, "bots": bots, "total": len(bots)}


async def bot_list() -> List[Dict[str, Any]]:
    bot = first_bot()
    if bot is None:
        return []
    status = await bot_status()
    chat = chat_statistics()
    calls = plugin_call_statistics()
    return [
        {
            "self_id": status["self_id"],
            "nickname": status["nickname"],
            "ava_url": status["ava_url"],
            "platform": "qq",
            "friend_count": status["friend_count"],
            "group_count": status["group_count"],
            "received_messages": chat["day"],
            "day_call": calls["day"],
            "connect_date": status["start_time"],
            "messages_total": chat["all"],
            "total_call": calls["all"],
        }
    ]


# ==================== 仪表盘 ====================
async def dashboard() -> Dict[str, Any]:
    status = await bot_status()
    plugins = plugin_service.get_plugin_list()
    chat = chat_statistics()
    calls = plugin_call_statistics()
    online = status["is_running"]
    return {
        "overview": {
            "bot_status": "online" if online else "offline",
            "uptime": status["uptime"],
            "uptime_formatted": status["uptime_formatted"],
            "group_count": status["group_count"],
            "friend_count": status["friend_count"],
            "message_count_today": chat["day"],
            "plugin_count": len(plugins),
            "enabled_plugin_count": sum(1 for p in plugins if p["enabled"]),
        },
        "stats": {
            "message_stats": {"label": "今日消息", "value": chat["day"], "trend": "stable", "change": 0},
            "user_stats": {"label": "活跃用户", "value": active_users_today(), "trend": "stable", "change": 0},
            "group_stats": {"label": "活跃群组", "value": len(group_message_counts()), "trend": "stable", "change": 0},
            "error_stats": {"label": "今日插件调用", "value": calls["day"], "trend": "stable", "change": 0},
        },
        "quick_actions": [
            {"name": "文件管理", "description": "浏览与编辑项目文件", "icon": "Folder", "action_type": "files"},
            {"name": "插件管理", "description": "查看并开关插件", "icon": "Grid", "action_type": "plugin"},
            {"name": "运行日志", "description": "实时查看 Bot 日志", "icon": "Document", "action_type": "logs"},
            {"name": "数据分析", "description": "消息与调用趋势", "icon": "DataLine", "action_type": "analytics"},
        ],
        "system_health": system_service.get_health()["status"],
    }


async def dashboard_statistics() -> Dict[str, Any]:
    groups = await group_list()
    counts = group_message_counts(30)
    group_items = [
        {
            "group_id": g["group_id"],
            "group_name": g["group_name"],
            "message_count": counts.get(g["group_id"], 0),
            "plugin_call_count": 0,
        }
        for g in groups
    ]
    group_items.sort(key=lambda x: x["message_count"], reverse=True)

    friends = []
    for user in sorted(message_stats().items(), key=lambda kv: int(kv[1].get("total", 0)), reverse=True)[:20]:
        uid, stats = user
        profile = load_user(uid)
        friends.append(
            {
                "user_id": uid,
                "user_name": profile.get("nickname") or uid,
                "message_count": int(stats.get("total", 0)),
                "plugin_call_count": 0,
            }
        )
    return {"groups": group_items, "friends": friends}


# ==================== 历史更新（GitHub） ====================
async def github_commits(limit: int = 10) -> List[Dict[str, Any]]:
    """拉取 GitHub 仓库最近提交，供首页「历史更新」时间线展示。"""
    now = time.time()
    cached = _commits_cache.get("data") or []
    if cached and now - float(_commits_cache.get("ts") or 0) < _COMMITS_TTL:
        return cached[:limit]

    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
    headers = {
        "User-Agent": "MikuBot-WebUI",
        "Accept": "application/vnd.github+json",
    }
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get(url, params={"per_page": limit}, headers=headers)
            response.raise_for_status()
            items = response.json()
    except httpx.ConnectError as exc:
        # 本机证书链无法验证 GitHub（系统代理/证书库差异），降级为不校验证书；
        # 仅用于拉取公开仓库的提交展示，不涉及凭据传输。
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            logger.warning(f"[WebUI] 获取 GitHub 提交记录失败: {exc}")
            return cached[:limit]
        try:
            async with httpx.AsyncClient(
                timeout=8, follow_redirects=True, verify=False
            ) as client:
                response = await client.get(url, params={"per_page": limit}, headers=headers)
                response.raise_for_status()
                items = response.json()
        except Exception as retry_exc:
            logger.warning(f"[WebUI] 获取 GitHub 提交记录失败: {retry_exc}")
            return cached[:limit]
    except Exception as exc:
        logger.warning(f"[WebUI] 获取 GitHub 提交记录失败: {exc}")
        return cached[:limit]

    commits: List[Dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        user = item.get("author") or {}
        message = str(commit.get("message") or "").strip().splitlines()
        commits.append(
            {
                "sha": str(item.get("sha") or "")[:7],
                "date": author.get("date") or "",
                "author": author.get("name") or user.get("login") or "未知",
                "avatar_url": user.get("avatar_url") or "",
                "message": message[0][:200] if message else "",
            }
        )

    _commits_cache["ts"] = now
    _commits_cache["data"] = commits
    return commits[:limit]


# ==================== 数据分析 ====================
def _daily_range(start: datetime, end: datetime) -> List[str]:
    days = []
    cursor = start.date()
    while cursor <= end.date():
        days.append(cursor.strftime("%Y-%m-%d"))
        cursor += timedelta(days=1)
    return days


def analytics_trend(start: datetime, end: datetime, granularity: str = "day") -> Dict[str, Any]:
    days = _daily_range(start, end)
    msg_by_day: Dict[str, int] = {d: 0 for d in days}
    call_by_day: Dict[str, int] = {d: 0 for d in days}
    for stats in message_stats().values():
        for day, value in (stats.get("daily") or {}).items():
            if day in msg_by_day:
                msg_by_day[day] += int(value)
    for stats in plugin_stats().values():
        for day, value in (stats.get("__daily__") or {}).items():
            if day in call_by_day:
                call_by_day[day] += int(value)

    points = [
        {
            "timestamp": f"{day}T00:00:00",
            "message_count": msg_by_day[day],
            "plugin_call_count": call_by_day[day],
        }
        for day in days
    ]
    return {
        "data_points": points,
        "total_message_count": sum(msg_by_day.values()),
        "total_plugin_call_count": sum(call_by_day.values()),
        "granularity": granularity,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }


def analytics_statistics(start: datetime, end: datetime) -> Dict[str, Any]:
    days = set(_daily_range(start, end))
    groups: Dict[str, int] = {}
    friends = []
    for uid, stats in message_stats().items():
        count = sum(int(v) for d, v in (stats.get("daily") or {}).items() if d in days)
        if count <= 0:
            continue
        profile = load_user(uid)
        friends.append(
            {
                "user_id": uid,
                "user_name": profile.get("nickname") or uid,
                "message_count": count,
                "plugin_call_count": 0,
            }
        )
        total = int(stats.get("total", 0)) or 1
        for gid, gcount in (stats.get("groups") or {}).items():
            groups[gid] = groups.get(gid, 0) + int(count * int(gcount) / total)
    friends.sort(key=lambda x: x["message_count"], reverse=True)
    return {
        "groups": [
            {"group_id": gid, "group_name": gid, "message_count": count, "plugin_call_count": 0}
            for gid, count in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "friends": friends,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }


def _top10(key: str, cast) -> List[Dict[str, Any]]:
    rows = []
    for user in iter_users():
        uid = str(user.get("user_id", ""))
        try:
            value = cast(user.get(key, 0))
        except (TypeError, ValueError):
            value = 0
        if value <= 0:
            continue
        rows.append(
            {
                "user_id": uid,
                "user_name": user.get("nickname") or uid,
                key: value,
                "ava_url": user_avatar(uid),
            }
        )
    rows.sort(key=lambda x: x[key], reverse=True)
    return rows[:10]


def favorability_top10() -> List[Dict[str, Any]]:
    return _top10("favor", float)


def gold_top10() -> List[Dict[str, Any]]:
    return _top10("coins", int)


# ==================== 群设置 / 成员 ====================
def group_settings() -> Dict[str, Any]:
    data = _load_json(GROUP_SETTINGS_FILE)
    return data if isinstance(data, dict) else {}


def _group_setting(group_id: str) -> Dict[str, Any]:
    defaults = {
        "level": 5,
        "status": True,
        "is_super": False,
        "block_task": False,
        "block_plugin": False,
    }
    defaults.update(group_settings().get(group_id, {}))
    return defaults


def save_group_setting(group_id: str, updates: Dict[str, Any]) -> None:
    data = group_settings()
    item = data.get(group_id, {})
    item.update({k: v for k, v in updates.items() if v is not None})
    data[group_id] = item
    _save_json(GROUP_SETTINGS_FILE, data)


async def group_detail(group_id: str) -> Dict[str, Any]:
    bot = first_bot()
    settings = _group_setting(group_id)
    info = {}
    if bot is not None:
        try:
            info = await bot.get_group_info(group_id=int(group_id))
        except Exception:
            info = {}
    return {
        "group_id": group_id,
        "group_name": info.get("group_name") or settings.get("group_name") or group_id,
        "ava_url": f"https://p.qlogo.cn/gh/{group_id}/{group_id}/100",
        "member_count": int(info.get("member_count", 0)),
        "max_member_count": int(info.get("max_member_count", 0)),
        "level": int(settings.get("level", 5)),
        "status": bool(settings.get("status", True)),
        "is_super": bool(settings.get("is_super", False)),
        "block_task": bool(settings.get("block_task", False)),
        "block_plugin": bool(settings.get("block_plugin", False)),
    }


async def group_members(group_id: str) -> List[Dict[str, Any]]:
    bot = first_bot()
    if bot is None:
        return []
    try:
        members = await bot.get_group_member_list(group_id=int(group_id))
    except Exception:
        return []
    return [
        {
            "user_id": str(m.get("user_id", "")),
            "nickname": m.get("nickname", ""),
            "remark": m.get("card", ""),
            "ava_url": user_avatar(str(m.get("user_id", ""))),
            "role": m.get("role", "member"),
        }
        for m in members
    ]


def member_detail(user_id: str, group_id: str = "") -> Dict[str, Any]:
    profile = load_user(user_id)
    return {
        "user_id": user_id,
        "nickname": profile.get("nickname") or user_id,
        "remark": profile.get("uid") or "",
        "ava_url": user_avatar(user_id),
        "gold": int(profile.get("coins", 0)),
        "favorability": float(profile.get("favor", 0)),
        "is_banned": bool(profile.get("is_banned", False)),
    }


def update_member(user_id: str, group_id: str, gold=None, favorability=None, is_banned=None) -> bool:
    profile = load_user(user_id) or {"user_id": user_id}
    if gold is not None:
        profile["coins"] = int(gold)
    if favorability is not None:
        profile["favor"] = float(favorability)
    if is_banned is not None:
        profile["is_banned"] = bool(is_banned)
    save_user(user_id, profile)
    return True


def group_plugins(group_id: str) -> List[Dict[str, Any]]:
    from .config_service import load_blacklist

    disabled = load_blacklist().get("group_disabled", {}).get(group_id, [])
    result = []
    for plugin in plugin_service.get_plugin_list():
        module = plugin["name"]
        result.append(
            {
                "module": module,
                "name": plugin["label"],
                "description": plugin.get("description", ""),
                "enabled": module not in disabled and plugin.get("enabled", True),
                "is_task": False,
            }
        )
    return result


def toggle_group_plugin(group_id: str, module: str, action: str) -> Dict[str, Any]:
    from .config_service import add_blacklist_item, remove_blacklist_item

    if action == "block":
        add_blacklist_item("group", group_id, module)
        return {"group_id": group_id, "module": module, "enabled": False}
    remove_blacklist_item("group", group_id, module)
    return {"group_id": group_id, "module": module, "enabled": True}


def group_statistics(group_id: str) -> Dict[str, Any]:
    bot_groups = group_message_counts(30)
    disabled = _load_json(DATA_DIR / "blacklist.json").get("group_disabled", {}).get(group_id, [])
    return {
        "group_id": group_id,
        "group_name": _group_setting(group_id).get("group_name", group_id),
        "chat_count": bot_groups.get(group_id, 0),
        "call_count": 0,
        "member_count": 0,
        "active_members": 0,
    }


# ==================== 申请 / 好友 ====================
def _read_requests() -> Dict[str, Any]:
    data = _load_json(REQUEST_FILE)
    if not isinstance(data, dict):
        return {"requests": [], "counter": 0}
    data.setdefault("requests", [])
    return data


def _write_requests(data: Dict[str, Any]) -> None:
    _save_json(REQUEST_FILE, data)


def request_list(bot_id: Optional[str] = None) -> Dict[str, Any]:
    data = _read_requests()
    friends, groups = [], []
    for item in data.get("requests", []):
        if item.get("handled"):
            continue
        uid = str(item.get("user_id", ""))
        nickname = item.get("user_name") or item.get("nickname") or uid
        base = {
            "bot_id": str(bot_id or ""),
            "oid": item.get("id", 0),
            "id": uid,
            "flag": item.get("flag", ""),
            "nickname": nickname,
            "comment": item.get("comment", ""),
            "ava_url": user_avatar(uid),
        }
        if item.get("type") == "group":
            groups.append(
                {
                    **base,
                    "type": "group",
                    "invite_group": str(item.get("group_id", "")),
                    "group_name": item.get("group_name", ""),
                }
            )
        else:
            friends.append({**base, "type": "friend"})
    return {"friend": friends, "group": groups}


async def handle_request(bot_id: Optional[str], request_id: int, action: str) -> bool:
    from . import manage_service

    if action == "approve":
        await manage_service.approve_request(int(request_id))
        return True
    if action in ("refused", "reject"):
        await manage_service.reject_request(int(request_id))
        return True
    # ignore：直接移除记录
    data = _read_requests()
    data["requests"] = [r for r in data.get("requests", []) if r.get("id") != request_id]
    _write_requests(data)
    return True


def clear_request(request_type: str) -> bool:
    data = _read_requests()
    if request_type in ("friend", "group"):
        data["requests"] = [r for r in data.get("requests", []) if r.get("type") != request_type]
    else:
        data["requests"] = []
    _write_requests(data)
    return True


def friend_detail(user_id: str, group_id: str = "") -> Dict[str, Any]:
    profile = load_user(user_id)
    return {
        "user_id": user_id,
        "nickname": profile.get("nickname") or user_id,
        "ava_url": user_avatar(user_id),
        "gold": int(profile.get("coins", 0)),
        "favorability": float(profile.get("favor", 0)),
    }


def friend_trend(user_id: str, days: int = 7) -> Dict[str, Any]:
    start = datetime.now() - timedelta(days=days - 1)
    path = DATA_DIR / "chat_history" / "private" / f"{user_id}.json"
    messages = _load_json(path)
    if isinstance(messages, dict):
        messages = messages.get("messages", [])
    day_counts: Dict[str, int] = {}
    if isinstance(messages, list):
        for message in messages:
            ts = message.get("time", 0)
            try:
                date = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                continue
            day_counts[date] = day_counts.get(date, 0) + 1

    points = []
    cursor = start
    while cursor.date() <= datetime.now().date():
        key = cursor.strftime("%Y-%m-%d")
        points.append(
            {
                "date": cursor.strftime("%m-%d"),
                "chat_count": day_counts.get(key, 0),
                "call_count": 0,
            }
        )
        cursor += timedelta(days=1)
    return {
        "data": points,
        "total_chat": sum(p["chat_count"] for p in points),
        "total_call": 0,
    }


# ==================== 插件列表 ====================
def plugin_items(search: str = "", status=None, plugin_type=None, page: int = 1, page_size: int = 50):
    items = []
    for index, plugin in enumerate(plugin_service.get_plugin_list(), start=1):
        module = plugin["name"]
        if search and search.lower() not in module.lower() and search.lower() not in plugin.get("label", "").lower():
            continue
        if status is not None and bool(plugin.get("enabled", True)) != bool(status):
            continue
        is_builtin = plugin.get("type") != "plugin"
        ptype = "builtin" if is_builtin else "normal"
        if plugin_type and plugin_type != ptype:
            continue
        items.append(
            {
                "id": index,
                "module": module,
                "name": plugin.get("label", module),
                "description": plugin.get("description", ""),
                "author": "MikuBot",
                "version": "1.0.0",
                "plugin_type": ptype,
                "is_enabled": bool(plugin.get("enabled", True)),
                "allow_switch": module != "bot",
                "allow_setting": True,
                "is_builtin": is_builtin,
            }
        )
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": start + page_size < total,
        "has_prev": page > 1,
    }


def plugin_config(module: str) -> Dict[str, Any]:
    detail = plugin_service.get_plugin_detail(module)
    from .config_meta import get_hint, get_label

    configs = []
    for item in detail.get("items", []):
        configs.append(
            {
                "module": module,
                "key": item["key"],
                "value": item.get("value", ""),
                "description": item.get("hint") or get_hint(module, item["key"]),
                "label": get_label(module, item["key"]),
            }
        )
    return {
        "module": module,
        "name": detail["plugin"].get("label", module),
        "configs": configs,
    }


def _config_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "str"


def plugin_detail(module: str) -> Dict[str, Any]:
    """参考前端插件配置弹窗需要的详情结构（config_list）。"""
    detail = plugin_service.get_plugin_detail(module)
    raw_config = detail.get("raw_config") or {}
    config_list = []
    for item in detail.get("items", []):
        key = item.get("key", "")
        if not key or key == "enabled":
            continue
        value = raw_config.get(key, "")
        config_list.append(
            {
                "key": key,
                "type": _config_type(value),
                "value": value,
                "help": item.get("hint") or item.get("label") or "",
                "default_value": None,
            }
        )
    detail["config_list"] = config_list
    return detail

