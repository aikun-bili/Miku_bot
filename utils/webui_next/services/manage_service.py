"""管理服务：群组、好友、申请与聊天记录。"""

import json
from datetime import datetime
from typing import Any, Dict, List

from nonebot.log import logger

from ..exceptions import NotFoundException, SystemException, ValidationException
from ..formatters import parse_datetime
from ..paths import DATA_DIR


def _first_bot():
    import nonebot

    bots = nonebot.get_bots()
    if not bots:
        raise SystemException("没有可用的 Bot")
    return next(iter(bots.values()))


def _load_msg_stats() -> Dict[str, Any]:
    path = DATA_DIR / "message_stats.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


async def fetch_groups() -> Dict[str, Any]:
    try:
        bot = _first_bot()
    except SystemException:
        return {"groups": []}
    group_list = await bot.get_group_list()

    group_msg_count: Dict[str, int] = {}
    for stats in _load_msg_stats().values():
        for gid, count in (stats.get("groups") or {}).items():
            group_msg_count[gid] = group_msg_count.get(gid, 0) + int(count)

    groups = []
    for group in group_list:
        gid = str(group.get("group_id", ""))
        groups.append(
            {
                "id": gid,
                "name": group.get("group_name", ""),
                "avatar": f"https://p.qlogo.cn/gh/{gid}/{gid}/100",
                "member_count": group.get("member_count", 0),
                "max_member_count": group.get("max_member_count", 0),
                "message_count": group_msg_count.get(gid, 0),
            }
        )
    return {"groups": groups}


async def fetch_users() -> Dict[str, Any]:
    try:
        bot = _first_bot()
    except SystemException:
        return {"users": []}
    friend_list = await bot.get_friend_list()
    from utils.avatar_cache import get_avatar_data_uri

    users = []
    for friend in friend_list:
        uid = str(friend.get("user_id", ""))
        nickname = friend.get("nickname", "")
        remark = friend.get("remark", "")
        display_name = remark or nickname
        try:
            avatar = await get_avatar_data_uri(uid, default_char=(display_name or "U")[0])
        except Exception:
            avatar = ""
        users.append({"id": uid, "nickname": display_name, "avatar": avatar})
    return {"users": users}


def _request_file():
    return DATA_DIR / "friend_requests.json"


def _expire_hours() -> int:
    try:
        from utils.config_manager import config_manager

        return int(config_manager.get("miku_friend_request", "expire_hours", 48))
    except Exception:
        return 48


def _read_requests() -> Dict[str, Any]:
    path = _request_file()
    if not path.exists():
        return {"requests": [], "counter": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"requests": [], "counter": 0}
        data.setdefault("requests", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"requests": [], "counter": 0}


def _write_requests(data: Dict[str, Any]) -> None:
    try:
        _request_file().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        raise SystemException(f"保存申请记录失败: {e}") from e


async def fetch_requests() -> Dict[str, Any]:
    """待处理的好友 / 群申请，自动过滤过期项。"""
    data = _read_requests()
    requests = data.get("requests", [])
    expire_hours = _expire_hours()
    now = datetime.now()

    active = []
    for item in requests:
        if item.get("handled"):
            continue
        if expire_hours > 0:
            requested_at = parse_datetime(item.get("time", ""))
            if (now - requested_at).total_seconds() > expire_hours * 3600:
                continue
        active.append(item)

    changed = len(active) != len(requests)
    data["requests"] = active
    if not active and data.get("counter", 0) != 0:
        data["counter"] = 0
        changed = True
    if changed:
        _write_requests(data)

    from utils.avatar_cache import get_avatar_data_uri

    for item in active:
        uid = str(item.get("user_id", ""))
        if uid and not item.get("avatar"):
            try:
                item["avatar"] = await get_avatar_data_uri(uid, default_char="U")
            except Exception:
                item["avatar"] = ""
        if item.get("type") == "group":
            gid = str(item.get("group_id", ""))
            if gid:
                item["group_avatar"] = f"https://p.qlogo.cn/gh/{gid}/{gid}/100"

    return {"requests": list(reversed(active)), "pending_count": len(active)}


def _find_request(data: Dict[str, Any], req_id: int) -> Dict[str, Any]:
    for item in data.get("requests", []):
        if item.get("id") == req_id:
            if item.get("handled"):
                action = item.get("action", "")
                messages = {
                    "approve": "该申请已同意",
                    "reject": "该申请已拒绝",
                    "expired": "该申请已过期失效",
                }
                raise ValidationException(messages.get(action, "该申请已处理"))
            return item
    raise NotFoundException("找不到该申请")


async def approve_request(req_id: int) -> Dict[str, Any]:
    bot = _first_bot()
    data = _read_requests()
    target = _find_request(data, req_id)

    try:
        if target.get("type") == "friend":
            await bot.set_friend_add_request(flag=target["flag"], approve=True)
        else:
            await bot.set_group_add_request(
                flag=target["flag"], sub_type=target.get("sub_type", "add"), approve=True
            )
    except Exception as e:
        message = str(e)
        if "already agree msg by self" in message.casefold():
            data["requests"] = [r for r in data["requests"] if r.get("id") != req_id]
            _write_requests(data)
            return {"message": "申请此前已同意，已同步本地状态"}
        if "no such request" in message.casefold() or "1200" in message:
            target["handled"] = True
            target["action"] = "expired"
            target["handle_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _write_requests(data)
            raise ValidationException("申请已失效（可能已过期或已通过其他方式处理）") from e
        raise SystemException(f"操作失败: {e}") from e

    data["requests"] = [r for r in data["requests"] if r.get("id") != req_id]
    _write_requests(data)
    return {"message": "已同意"}


async def reject_request(req_id: int, reason: str = "") -> Dict[str, Any]:
    bot = _first_bot()
    data = _read_requests()
    target = _find_request(data, req_id)

    try:
        if target.get("type") == "friend":
            await bot.set_friend_add_request(flag=target["flag"], approve=False)
        else:
            await bot.set_group_add_request(
                flag=target["flag"],
                sub_type=target.get("sub_type", "add"),
                approve=False,
                reason=reason,
            )
    except Exception as e:
        message = str(e)
        if "no such request" in message.casefold() or "1200" in message:
            target["handled"] = True
            target["action"] = "expired"
            target["handle_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _write_requests(data)
            raise ValidationException("申请已失效（可能已过期或已通过其他方式处理）") from e
        raise SystemException(f"操作失败: {e}") from e

    data["requests"] = [r for r in data["requests"] if r.get("id") != req_id]
    _write_requests(data)
    return {"message": "已拒绝"}


async def send_message(message_type: str, target_id: str, content: str) -> Dict[str, Any]:
    if not target_id or not content:
        raise ValidationException("目标ID和消息内容不能为空")
    bot = _first_bot()
    try:
        if message_type == "group":
            await bot.send_group_msg(group_id=int(target_id), message=content)
        else:
            await bot.send_private_msg(user_id=int(target_id), message=content)
    except Exception as e:
        logger.warning(f"[WebUI] 发送消息失败: {e}")
        raise SystemException(f"发送失败: {e}") from e
    return {"message": "发送成功"}


def get_chat_history(message_type: str, target_id: str, limit: int = 100) -> Dict[str, Any]:
    """合并普通聊天记录与 AI 对话记录。"""
    if not target_id:
        return {"messages": []}

    messages: List[Dict[str, Any]] = []
    for folder in ("chat_history", "ai_chat_history"):
        path = DATA_DIR / folder / message_type / f"{target_id}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            messages.extend(data if isinstance(data, list) else data.get("messages", []))
        except (OSError, json.JSONDecodeError):
            continue

    seen = set()
    unique = []
    for message in sorted(messages, key=lambda x: x.get("time", 0)):
        key = (message.get("time", 0), message.get("content", ""), message.get("role", ""))
        if key not in seen:
            seen.add(key)
            unique.append(message)
    return {"messages": unique[-max(1, limit):]}
