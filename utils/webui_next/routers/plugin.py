"""插件路由：列表、详情、配置与启停。"""

from typing import Any, Dict

from fastapi import APIRouter, Request

from ..exceptions import ValidationException
from ..responses import ok
from ..services import plugin_service

router = APIRouter(tags=["plugin"])


@router.get("/plugins", summary="插件列表")
async def plugins():
    return ok(plugin_service.list_plugins())


@router.get("/plugins/{name}", summary="插件详情")
async def plugin_detail(name: str):
    return ok(plugin_service.get_plugin_detail(name))


@router.put("/plugins/{name}", summary="保存插件配置")
async def plugin_update(name: str, request: Request):
    try:
        body: Dict[str, Any] = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    if not isinstance(body, dict):
        raise ValidationException("请求格式错误")
    return ok(plugin_service.update_plugin(name, body), "保存成功")


@router.get("/plugin/list", summary="插件列表（v1）")
@router.post("/plugin/list", summary="插件列表（v1）")
async def plugin_list():
    plugins = plugin_service.get_plugin_list()
    items = []
    for item in plugins:
        module = item.get("name", "")
        items.append(
            {
                "module": module,
                "name": item.get("label", module),
                "description": item.get("description", ""),
                "enabled": item.get("enabled", True),
                "is_builtin": item.get("type") != "plugin",
                "type": item.get("type", "plugin"),
                "version": "1.0.0",
                "author": "",
                "category": "other",
            }
        )
    return ok(
        {
            "items": items,
            "plugins": items,
            "total": len(items),
            "total_enabled": sum(1 for i in items if i["enabled"]),
            "total_disabled": sum(1 for i in items if not i["enabled"]),
            "total_builtin": sum(1 for i in items if i["is_builtin"]),
        }
    )


@router.post("/plugin/toggle", summary="切换插件状态")
async def plugin_toggle(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    module = str(body.get("module", "")).strip()
    enable = bool(body.get("enable", True))
    return ok(plugin_service.toggle_plugin(module, enable))


@router.get("/plugin/detail/{module}", summary="插件详情（v1）")
async def plugin_detail_v1(module: str):
    return ok(plugin_service.get_plugin_detail(module)["plugin"])


@router.get("/plugin/config/{module}", summary="插件配置（v1）")
async def plugin_config_v1(module: str):
    return ok(plugin_service.get_plugin_config_items(module))
