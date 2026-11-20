"""配置路由：bot.yaml、AI 模型配置、备份恢复与黑名单。"""

from fastapi import APIRouter, Request

from ..exceptions import ValidationException
from ..responses import ok
from ..services import auth_service, config_service

router = APIRouter(tags=["config"])


@router.get("/config", summary="读取配置")
async def get_config(target: str = "bot"):
    return ok(config_service.read_config(target))


@router.put("/config", summary="保存配置")
async def update_config(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    content = body.get("content", "")
    target = str(body.get("target", "bot"))
    return ok(config_service.update_config(content, target), "配置已保存")


@router.post("/config/backup/{timestamp}/restore", summary="从备份恢复")
async def restore_backup(timestamp: str, target: str = "bot"):
    return ok(config_service.restore_backup(timestamp, target), "恢复成功")


@router.get("/config/env/list", summary="环境变量列表")
async def env_list():
    envs = [
        {"key": key, "value": value}
        for key, value in auth_service.read_env_keys().items()
    ]
    return ok({"envs": envs})


@router.get("/config/yaml", summary="YAML 原文")
async def config_yaml():
    return ok({"content": config_service.read_config("bot")["content"]})


@router.get("/blacklist", summary="黑名单")
async def blacklist():
    return ok(config_service.load_blacklist())


@router.put("/blacklist", summary="保存黑名单")
async def update_blacklist(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    data = config_service.load_blacklist()
    if isinstance(body.get("global_disabled"), list):
        data["global_disabled"] = body["global_disabled"]
    if isinstance(body.get("group_disabled"), dict):
        data["group_disabled"] = body["group_disabled"]
    if isinstance(body.get("user_disabled"), dict):
        data["user_disabled"] = body["user_disabled"]
    config_service.save_blacklist(data)
    return ok(data, "已保存")


@router.post("/blacklist/group/{group_id}", summary="添加群黑名单")
async def add_group_blacklist(group_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    plugin = (body.get("plugin") or request.query_params.get("plugin", "")).strip()
    return ok(config_service.add_blacklist_item("group", group_id, plugin), "已添加")


@router.delete("/blacklist/group/{group_id}/{plugin}", summary="移除群黑名单")
async def remove_group_blacklist(group_id: str, plugin: str):
    return ok(config_service.remove_blacklist_item("group", group_id, plugin), "已移除")


@router.post("/blacklist/user/{user_id}", summary="添加用户黑名单")
async def add_user_blacklist(user_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    plugin = (body.get("plugin") or request.query_params.get("plugin", "")).strip()
    return ok(config_service.add_blacklist_item("user", user_id, plugin), "已添加")


@router.delete("/blacklist/user/{user_id}/{plugin}", summary="移除用户黑名单")
async def remove_user_blacklist(user_id: str, plugin: str):
    return ok(config_service.remove_blacklist_item("user", user_id, plugin), "已移除")
