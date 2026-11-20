"""参考前端（/next）兼容 API。

路径统一为 ``/miku/api/v1``（旧前缀保留为兼容别名），响应结构与参考项目保持一致，
数据全部来自 miku_bot 现有的 JSON / SQLite / NoneBot 运行时。
"""

import base64
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from .. import database
from ..exceptions import APIException, NotFoundException, ValidationException
from ..paths import BASE_DIR, CONFIG_FILE
from ..responses import ok
from ..services import (
    auth_service,
    config_service,
    file_service,
    manage_service,
    plugin_service,
    spa_service,
    system_service,
)
from ..dependencies import require_auth
from pydantic import BaseModel, Field

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}

auth_router = APIRouter(tags=["V1 认证"])
router = APIRouter(tags=["V1 兼容"], dependencies=[Depends(require_auth)])


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


async def _body(request: Request) -> Dict[str, Any]:
    try:
        data = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    return data if isinstance(data, dict) else {}


# ==================== 认证 ====================
class LoginBody(BaseModel):
    username: str = ""
    password: str = ""
    token: str = ""


@auth_router.get("/system/ping")
async def ping():
    return ok({"message": "pong"})


@auth_router.post("/auth/login")
async def login(payload: LoginBody, request: Request):
    password = payload.password or payload.token
    data = auth_service.login(password, client_ip=getattr(request.client, "host", "unknown"))
    return ok(
        {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_type": "bearer",
            "expires_in": data["expires_in"],
            "device_token": data["device_token"],
        },
        "登录成功",
    )


@auth_router.get("/auth/verify")
async def verify(token: str = ""):
    data = auth_service.verify(token)
    return ok({"valid": True, "username": data.get("username", "admin")})


@auth_router.post("/auth/refresh")
async def refresh(token: str = "", request: Request = None):
    if not token and request is not None:
        token = (request.query_params.get("token") or "").strip()
        if not token:
            body = await _body(request) if request.headers.get("content-type", "").startswith("application/json") else {}
            token = str(body.get("refresh_token") or body.get("token") or "")
    if not token:
        raise APIException("缺少 token", code=401)
    payload = auth_service.refresh_compat(token)
    return ok(
        {
            "access_token": payload["access_token"],
            "refresh_token": payload["refresh_token"],
            "token_type": "bearer",
            "expires_in": payload["expires_in"],
        },
        "Token 刷新成功",
    )


# ==================== 系统 ====================
@router.get("/system/status")
async def system_status():
    status = system_service.get_status()
    return ok(
        {
            "cpu": status["cpu"],
            "memory": status["memory"],
            "disk": status["disk"],
            "check_time": _iso(datetime.now()),
        }
    )


@router.get("/system/health")
async def system_health():
    health = system_service.get_health()
    cpu, memory, disk = health["cpu_usage"], health["memory_usage"], health["disk_usage"]

    def level(value: float) -> str:
        return "critical" if value >= 90 else "high" if value >= 75 else "normal"

    recommendations = []
    if cpu >= 75:
        recommendations.append("CPU 占用较高，建议检查高负载插件")
    if memory >= 75:
        recommendations.append("内存占用较高，可重启 Bot 释放内存")
    if disk >= 80:
        recommendations.append("磁盘空间不足，建议清理缓存与日志")
    return ok(
        {
            "status": health["status"],
            "cpu_status": level(cpu),
            "memory_status": level(memory),
            "disk_status": level(disk),
            "recommendations": recommendations,
        }
    )


@router.get("/system/bot-status")
async def system_bot_status(bot_id: Optional[str] = None):
    return ok(await spa_service.bot_status(bot_id))


@router.get("/system/network")
async def system_network():
    network = system_service.get_network()
    return ok(
        {
            "host": network["host"],
            "port": network["port"],
            "addresses": network["addresses"],
            "status": "ok",
            "latency": 0,
        }
    )


@router.get("/system/info")
async def system_info():
    info = system_service.get_info()
    bots = spa_service.bot_count()
    info.update(
        {
            "bot_count": bots,
            "plugin_count": len(plugin_service.get_plugin_list()),
            "config_exists": CONFIG_FILE.exists(),
        }
    )
    return ok(info)


@router.post("/system/restart")
async def system_restart():
    system_service.restart_bot()
    return ok(True, "开始重启 Bot...")


# ==================== 主页 ====================
@router.get("/main/bot-status")
async def main_bot_status(bot_id: Optional[str] = None):
    return ok(await spa_service.bot_status(bot_id))


@router.get("/main/bot-status/list")
async def main_bot_status_list(bot_id: Optional[str] = None):
    return ok(await spa_service.bot_status_list(bot_id))


@router.get("/main/bot-list")
async def main_bot_list():
    return ok(await spa_service.bot_list())


@router.get("/main/chat-statistics")
async def main_chat_statistics(bot_id: Optional[str] = None):
    return ok(spa_service.chat_statistics())


@router.get("/main/plugin-statistics")
async def main_plugin_statistics(bot_id: Optional[str] = None):
    return ok(spa_service.plugin_call_statistics())


@router.get("/main/active-groups")
async def main_active_groups(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    date_type: str = "week",
    bot_id: Optional[str] = None,
):
    days = {"day": 1, "week": 7, "month": 30, "year": 365}.get(date_type, 7)
    counts = spa_service.group_message_counts(days)
    groups = {g["group_id"]: g["group_name"] for g in await spa_service.group_list()}
    items = [
        {
            "group_id": gid,
            "name": groups.get(gid, gid),
            "chat_num": count,
            "ava_img": f"https://p.qlogo.cn/gh/{gid}/{gid}/100",
        }
        for gid, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    ]
    return ok(items)


@router.get("/main/hot-plugins")
async def main_hot_plugins(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    date_type: str = "week",
    bot_id: Optional[str] = None,
):
    stats = spa_service.plugin_stats()
    labels = {p["name"]: p["label"] for p in plugin_service.get_plugin_list()}
    items = [
        {
            "plugin_name": labels.get(module, module),
            "module": module,
            "call_count": int(value.get("__total__", 0)),
        }
        for module, value in stats.items()
        if isinstance(value, dict)
    ]
    items.sort(key=lambda x: x["call_count"], reverse=True)
    return ok(items[:10])


# ==================== 仪表盘 ====================
@router.get("/dashboard")
async def get_dashboard():
    return ok(await spa_service.dashboard())


@router.get("/dashboard/statistics")
async def get_dashboard_statistics():
    return ok(await spa_service.dashboard_statistics())


@router.get("/dashboard/commits")
async def get_dashboard_commits():
    return ok(await spa_service.github_commits())


# ==================== 插件 ====================
@router.post("/plugin/list")
async def plugin_list(request: Request):
    body = await _body(request) if await request.body() else {}
    result = spa_service.plugin_items(
        search=str(body.get("search") or ""),
        status=body.get("status"),
        plugin_type=body.get("plugin_type"),
        page=int(body.get("page") or 1),
        page_size=int(body.get("page_size") or 50),
    )
    return ok(result)


@router.post("/plugin/toggle")
async def plugin_toggle(request: Request):
    body = await _body(request)
    module = str(body.get("module") or "")
    if not module:
        raise ValidationException("缺少 module")
    plugin_service.toggle_plugin(module, bool(body.get("enable", True)))
    return ok(True, "状态已更新")


@router.get("/plugin/config/{module}")
async def plugin_config(module: str):
    return ok(spa_service.plugin_config(module))


@router.get("/plugin/detail/{module}")
async def plugin_detail(module: str):
    detail = spa_service.plugin_detail(module)
    return ok(detail)


@router.post("/config/plugin/batch")
async def plugin_batch_save(request: Request):
    body = await _body(request)
    module = str(body.get("module") or "")
    configs = body.get("configs") or {}
    if not module or not isinstance(configs, dict):
        raise ValidationException("参数错误")
    items = [
        {"key": key, "value": config_service.value_to_input(value)}
        for key, value in configs.items()
    ]
    plugin_service.update_plugin(module, {"items": items})
    return ok(True, "保存成功")


# ==================== 配置 ====================
@router.get("/config/env")
async def get_env(name: str = ".env"):
    if not name.startswith(".env") or "/" in name or "\\" in name:
        raise ValidationException("非法文件名")
    path = BASE_DIR / name
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return ok({"name": name, "content": content})


@router.post("/config/env")
async def save_env(request: Request):
    body = await _body(request)
    name = str(body.get("name") or ".env")
    if not name.startswith(".env") or "/" in name or "\\" in name:
        raise ValidationException("非法文件名")
    (BASE_DIR / name).write_text(str(body.get("content") or ""), encoding="utf-8")
    return ok(True, "保存成功")


@router.get("/config/yaml")
async def get_yaml():
    return ok({"file_path": str(CONFIG_FILE), "content": config_service.read_config("bot")["content"]})


@router.post("/config/yaml")
async def save_yaml(request: Request):
    body = await _body(request)
    content = body.get("content") if isinstance(body.get("content"), str) else body.get("data")
    if not isinstance(content, str):
        content = str(body.get("content") or "")
    config_service.update_config(content, "bot")
    return ok(True, "保存成功")


@router.get("/config/value")
async def get_config_value(module: str, key: str):
    data = config_service.load_yaml().get(module, {})
    return ok(data.get(key) if isinstance(data, dict) else None)


@router.post("/config/value")
async def set_config_value(request: Request):
    body = await _body(request)
    module = str(body.get("module") or "")
    key = str(body.get("key") or "")
    if not module or not key:
        raise ValidationException("参数错误")
    data = config_service.load_yaml()
    if not isinstance(data.get(module), dict):
        data[module] = {}
    data[module][key] = config_service.input_to_value(body.get("value"))
    config_service.save_yaml(data)
    config_service.reload_config_manager()
    return ok(True, "设置成功")


@router.post("/config/restart")
async def config_restart():
    system_service.restart_bot()
    return ok(True, "开始重启 Bot...")


# ==================== 管理 ====================
@router.get("/manage/friend-list")
async def manage_friend_list(bot_id: Optional[str] = None):
    return ok(await spa_service.friend_list(bot_id))


@router.get("/manage/group-list")
async def manage_group_list(bot_id: Optional[str] = None):
    return ok(await spa_service.group_list(bot_id))


@router.post("/manage/send-message")
async def manage_send_message(request: Request):
    body = await _body(request)
    bot = spa_service.first_bot()
    if bot is None:
        raise APIException("没有可用的 Bot")
    message = str(body.get("message") or "")
    if not message:
        raise ValidationException("消息不能为空")
    try:
        if body.get("group_id"):
            await bot.send_group_msg(group_id=int(body["group_id"]), message=message)
        elif body.get("user_id"):
            await bot.send_private_msg(user_id=int(body["user_id"]), message=message)
        else:
            raise ValidationException("缺少接收者")
    except ValidationException:
        raise
    except Exception as e:
        raise APIException(f"发送失败：{e}", code=500) from e
    return ok(True)


@router.post("/manage/leave-group")
async def manage_leave_group(request: Request):
    body = await _body(request)
    bot = spa_service.first_bot()
    if bot is None:
        raise APIException("没有可用的 Bot")
    try:
        await bot.set_group_leave(group_id=int(body.get("group_id", 0)))
    except Exception as e:
        raise APIException(f"退群失败：{e}", code=500) from e
    return ok(True)


@router.post("/manage/delete-friend")
async def manage_delete_friend(request: Request):
    body = await _body(request)
    bot = spa_service.first_bot()
    if bot is None:
        raise APIException("没有可用的 Bot")
    user_id = int(body.get("user_id", 0))
    try:
        await bot.call_api("delete_friend", user_id=user_id)
    except Exception as e:
        raise APIException(f"删除好友失败：{e}", code=500) from e
    return ok(True)


@router.get("/manage/group-detail")
async def manage_group_detail(group_id: str, bot_id: Optional[str] = None):
    return ok(await spa_service.group_detail(group_id))


@router.post("/manage/update-group")
async def manage_update_group(request: Request):
    body = await _body(request)
    group_id = str(body.get("group_id") or "")
    if not group_id:
        raise ValidationException("缺少 group_id")
    spa_service.save_group_setting(group_id, body)
    return ok(True)


@router.get("/manage/group-members")
async def manage_group_members(group_id: str, bot_id: Optional[str] = None):
    return ok(await spa_service.group_members(group_id))


@router.get("/manage/member-detail")
async def manage_member_detail(user_id: str, group_id: str = ""):
    return ok(spa_service.member_detail(user_id, group_id))


@router.post("/manage/update-member")
async def manage_update_member(request: Request):
    body = await _body(request)
    spa_service.update_member(
        str(body.get("user_id") or ""),
        str(body.get("group_id") or ""),
        body.get("gold"),
        body.get("favorability"),
        body.get("is_banned"),
    )
    return ok(True)


@router.get("/manage/group-plugins")
async def manage_group_plugins(group_id: str):
    return ok(spa_service.group_plugins(group_id))


@router.post("/manage/toggle-group-plugin")
async def manage_toggle_group_plugin(request: Request):
    body = await _body(request)
    return ok(
        spa_service.toggle_group_plugin(
            str(body.get("group_id") or ""),
            str(body.get("module") or ""),
            str(body.get("action") or "block"),
        )
    )


@router.get("/manage/group-statistics")
async def manage_group_statistics(group_id: str, bot_id: Optional[str] = None):
    return ok(spa_service.group_statistics(group_id))


@router.get("/manage/blacklist")
async def manage_blacklist(group_id: str = ""):
    data = config_service.load_blacklist()
    if not group_id:
        return ok([])
    entries = data.get("group_disabled", {}).get(group_id, [])
    return ok([{"module": module, "plugin_name": module} for module in entries])


@router.post("/manage/add-blacklist")
async def manage_add_blacklist(request: Request):
    body = await _body(request)
    user_id = str(body.get("user_id") or "")
    group_id = str(body.get("group_id") or "")
    if user_id:
        config_service.add_blacklist_item("user", user_id, "__all__")
    if group_id:
        config_service.add_blacklist_item("group", group_id, "__all__")
    return ok(True)


@router.post("/manage/remove-blacklist")
async def manage_remove_blacklist(request: Request):
    body = await _body(request)
    user_id = str(body.get("user_id") or "")
    group_id = str(body.get("group_id") or "")
    if user_id:
        config_service.remove_blacklist_item("user", user_id, "__all__")
    if group_id:
        config_service.remove_blacklist_item("group", group_id, "__all__")
    return ok(True)


@router.get("/manage/plugin-permissions")
async def manage_plugin_permissions(group_id: str = ""):
    return ok([])


@router.post("/manage/update-plugin-permissions")
async def manage_update_plugin_permissions(request: Request):
    await _body(request)
    return ok(True)


@router.get("/manage/request-list")
async def manage_request_list(bot_id: Optional[str] = None):
    return ok(spa_service.request_list(bot_id))


@router.post("/manage/handle-request")
async def manage_handle_request(request: Request):
    body = await _body(request)
    try:
        await spa_service.handle_request(
            body.get("bot_id"), int(body.get("id", 0)), str(body.get("action") or "approve")
        )
    except Exception as e:
        raise APIException(f"处理失败：{e}", code=500) from e
    return ok(True)


@router.post("/manage/clear-request")
async def manage_clear_request(request: Request):
    body = await _body(request)
    spa_service.clear_request(str(body.get("request_type") or ""))
    return ok(True)


@router.get("/manage/friend-detail")
async def manage_friend_detail(user_id: str, bot_id: Optional[str] = None):
    return ok(spa_service.friend_detail(user_id))


@router.post("/manage/update-friend")
async def manage_update_friend(request: Request):
    body = await _body(request)
    user_id = str(body.get("user_id") or "")
    profile = spa_service.load_user(user_id) or {"user_id": user_id}
    if body.get("gold") is not None:
        profile["coins"] = int(body["gold"])
    if body.get("favorability") is not None:
        profile["favor"] = float(body["favorability"])
    spa_service.save_user(user_id, profile)
    return ok(True)


@router.get("/manage/friend-trend")
async def manage_friend_trend(user_id: str, days: int = Query(default=7, ge=1, le=90)):
    return ok(spa_service.friend_trend(user_id, days))


# ==================== 数据分析 ====================
@router.get("/analytics/trend")
async def analytics_trend(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    granularity: str = "day",
    bot_id: Optional[str] = None,
):
    end = end_time or datetime.now()
    start = start_time or (end - timedelta(days=6))
    return ok(spa_service.analytics_trend(start, end, granularity))


@router.get("/analytics/statistics")
async def analytics_statistics(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    bot_id: Optional[str] = None,
):
    end = end_time or datetime.now()
    start = start_time or (end - timedelta(days=6))
    return ok(spa_service.analytics_statistics(start, end))


@router.get("/analytics/favorability-top10")
async def analytics_favorability(bot_id: Optional[str] = None):
    return ok(spa_service.favorability_top10())


@router.get("/analytics/gold-top10")
async def analytics_gold(bot_id: Optional[str] = None):
    return ok(spa_service.gold_top10())


# ==================== 文件 ====================
def _normalize_path(path: Optional[str]) -> str:
    value = (path or "").replace("\\", "/").strip("/")
    return "" if value in ("", ".") else value


@router.get("/file/list")
async def file_list(path: Optional[str] = None):
    data = file_service.list_dir(_normalize_path(path))
    files = []
    for item in data["items"]:
        suffix = Path(item["name"]).suffix.lower()
        files.append(
            {
                "name": item["name"],
                "is_file": not item["is_dir"],
                "is_image": suffix in IMAGE_SUFFIXES,
                "size": item["size"] or None,
                "size_formatted": item["size_str"] if not item["is_dir"] else None,
                "mtime": item["modified"].replace(" ", "T"),
                "mtime_formatted": item["modified"],
                "path": item["path"],
                "parent": data.get("parent"),
            }
        )
    current = data["path"]
    segments = [] if current in ("", ".") else current.split("/")
    return ok(
        {
            "files": files,
            "current_path": current,
            "path_segments": segments,
            "has_parent": data.get("parent") is not None,
        }
    )


@router.get("/file/read")
async def file_read(file_path: str, as_image: bool = False):
    data = file_service.read_file(file_path) if not as_image else None
    if as_image:
        from ..path_validator import ensure_file

        path = ensure_file(file_path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return ok({"path": file_path, "content": f"data:{mime};base64,{encoded}", "encoding": "base64"})
    return ok({"path": data["path"], "content": data["content"], "encoding": "utf-8"})


@router.post("/file/save")
async def file_save(request: Request):
    body = await _body(request)
    file_service.save_file(str(body.get("file_path") or ""), str(body.get("content") or ""))
    return ok(True, "保存成功")


@router.post("/file/delete")
async def file_delete(request: Request):
    body = await _body(request)
    file_service.delete_path(str(body.get("file_path") or ""))
    return ok(True, "删除成功")


@router.post("/file/delete-folder")
async def file_delete_folder(request: Request):
    body = await _body(request)
    file_service.delete_path(str(body.get("folder_path") or body.get("file_path") or ""))
    return ok(True, "删除成功")


@router.post("/file/rename")
async def file_rename(request: Request):
    body = await _body(request)
    file_service.rename_path(str(body.get("source_path") or ""), str(body.get("new_name") or ""))
    return ok(True, "重命名成功")


@router.post("/file/create-file")
async def file_create(request: Request):
    body = await _body(request)
    file_service.create_file(str(body.get("parent_path") or ""), str(body.get("name") or ""))
    return ok(True, "创建成功")


@router.post("/file/create-folder")
async def file_create_folder(request: Request):
    body = await _body(request)
    file_service.create_folder(str(body.get("parent_path") or ""), str(body.get("name") or ""))
    return ok(True, "创建成功")


# ==================== 数据库 ====================
@router.get("/database/tables")
async def database_tables():
    return ok(database.list_tables())


@router.get("/database/tables/{table_name}/columns")
async def database_columns(table_name: str):
    return ok(database.table_columns(table_name))


@router.get("/database/tables/{table_name}/data")
async def database_data(table_name: str, page: int = 1, page_size: int = 50):
    data = database.table_data(table_name, page, page_size)
    items = []
    for index, row in enumerate(data["data"]):
        row_id = row.get("id") or row.get("user_id") or row.get("group_id") or index + 1
        items.append({"id": row_id, "data": row})
    return ok(
        {
            "items": items,
            "total": data["total"],
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < data["total"],
            "has_prev": page > 1,
        }
    )


@router.post("/database/execute")
async def database_execute(request: Request):
    body = await _body(request)
    try:
        result = database.execute(str(body.get("sql") or ""))
    except (APIException, NotFoundException, ValidationException):
        raise
    except Exception as e:
        raise APIException(f"SQL 执行错误：{e}", code=400) from e
    rows = result.get("rows")
    return ok(
        {
            "success": True,
            "message": "执行成功",
            "data": rows,
            "rows_affected": result.get("rowcount", 0) if rows is None else None,
        }
    )


# ==================== 插件商店 ====================
@router.get("/store/get-plugin-store")
async def store_get():
    """本地插件全部视为「已安装」，用于商店页展示与统计。"""
    plugins = []
    modules = []
    for index, plugin in enumerate(plugin_service.get_plugin_list(), start=1):
        module = plugin.get("name", "")
        modules.append(module)
        plugins.append(
            {
                "id": index,
                "name": plugin.get("label") or module,
                "module": module,
                "description": plugin.get("description") or "",
                "version": "1.0.0",
                "author": "MikuBot",
                "is_installed": True,
                "plugin_type": "NORMAL" if plugin.get("type") == "plugin" else "ADMIN",
                "tags": ["本地"],
                "homepage": "",
            }
        )
    return ok({"install_module": modules, "plugin_list": plugins})


@router.post("/store/install")
@router.post("/store/update")
@router.post("/store/remove")
async def store_unsupported():
    raise APIException("本地插件已随项目部署，暂不支持在线安装/更新", code=400)


__all__ = ["auth_router", "router"]
