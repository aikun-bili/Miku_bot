"""插件服务：插件扫描、详情、配置读写与启停。"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from nonebot.log import logger

from ..exceptions import ConfigException, NotFoundException, ValidationException
from ..paths import BASE_DIR, DATA_DIR
from utils.ai_model_config import (
    AI_MODEL_CONFIG_KEYS,
    get_ai_model_config,
    migrate_legacy_ai_config,
    save_ai_model_config,
)

from .config_meta import (
    CONFIG_LABELS,
    SECTION_META,
    get_hint,
    get_label,
    get_section_description,
    get_section_label,
)
from .config_service import (
    input_to_value,
    load_yaml,
    reload_config_manager,
    save_yaml,
    value_to_input,
)

PLUGINS_DIR = BASE_DIR / "plugins"


def parse_plugin_meta(init_path: Path) -> Tuple[str, str]:
    """从插件 ``__init__.py`` 的 ``__plugin_meta__`` 中读取名称和描述。"""
    try:
        content = init_path.read_text(encoding="utf-8", errors="ignore")
        name_match = re.search(r'name\s*=\s*"([^"]*)"', content)
        desc_match = re.search(r'description\s*=\s*"([^"]*)"', content)
        return (
            name_match.group(1).strip() if name_match else "",
            desc_match.group(1).strip() if desc_match else "",
        )
    except OSError:
        return "", ""


def get_plugin_list() -> List[Dict[str, Any]]:
    """扫描 plugins 目录并合并已知配置节。"""
    config = load_yaml()
    sections: Dict[str, Dict[str, str]] = {}

    if PLUGINS_DIR.exists():
        for plugin_path in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_path.is_dir() or plugin_path.name.startswith("_"):
                continue
            if (plugin_path / "__init__.py").exists():
                sections[plugin_path.name] = {"name": plugin_path.name, "type": "plugin"}

    for section_name in SECTION_META:
        sections.setdefault(section_name, {"name": section_name, "type": "config"})

    plugins: List[Dict[str, Any]] = []
    for name in sorted(sections):
        plugin_config = config.get(name, {}) if isinstance(config, dict) else {}
        if not isinstance(plugin_config, dict):
            plugin_config = {}
        enabled = plugin_config.get("enabled", True)
        label = get_section_label(name)
        description = get_section_description(name)

        init_path = PLUGINS_DIR / name / "__init__.py"
        if init_path.exists():
            meta_name, meta_desc = parse_plugin_meta(init_path)
            label = meta_name or label
            description = meta_desc or description

        plugins.append(
            {
                "name": name,
                "label": label,
                "enabled": enabled,
                "description": description,
                "has_toggle": SECTION_META.get(name, {}).get("has_toggle", True) and name != "bot",
                "type": sections[name]["type"],
            }
        )
    return plugins


def _load_plugin_stats() -> Dict[str, Any]:
    path = DATA_DIR / "plugin_stats.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def list_plugins() -> Dict[str, Any]:
    """插件列表（附带调用次数）。"""
    stats = _load_plugin_stats()
    plugins = []
    for plugin in get_plugin_list():
        name = plugin.get("name", "")
        plugin_stats = stats.get(name, {})
        plugin["call_count"] = int(plugin_stats.get("__total__", 0))
        plugin["command_calls"] = plugin_stats.get("__commands__", {})
        plugins.append(plugin)
    return {"plugins": plugins}


def get_plugin_detail(name: str) -> Dict[str, Any]:
    """插件详情 + 表单项。"""
    plugin_info = next((p for p in get_plugin_list() if p["name"] == name), None)
    if plugin_info is None:
        raise NotFoundException("插件不存在")

    config = load_yaml()
    raw_config = config.get(name, {}) if isinstance(config, dict) else {}
    if not isinstance(raw_config, dict):
        raw_config = {}

    field_comments: Dict[str, str] = {}
    try:
        from utils.config_manager import config_manager

        field_comments = config_manager.get_field_comments(name) or {}
    except Exception:
        pass

    items: List[Dict[str, Any]] = []
    seen = set()
    for key, value in raw_config.items():
        seen.add(key)
        hint = get_hint(name, key) or field_comments.get(key, "")
        items.append(
            {
                "key": key,
                "label": get_label(name, key),
                "hint": hint,
                "value": value_to_input(value),
                "original_type": type(value).__name__,
                "is_list": isinstance(value, list),
            }
        )

    for key, info in CONFIG_LABELS.get(name, {}).items():
        if key in seen:
            continue
        meta = info if isinstance(info, dict) else {}
        hint = meta.get("hint", "") or field_comments.get(key, "")
        items.append(
            {
                "key": key,
                "label": meta.get("label", key),
                "hint": hint,
                "value": "",
                "original_type": "missing",
                "is_list": False,
            }
        )

    return {
        "plugin": plugin_info,
        "items": items,
        "raw_config": raw_config,
        "ai_model_config": get_ai_model_config() if name == "miku_ai" else None,
    }


def toggle_plugin(module: str, enable: bool) -> Dict[str, Any]:
    if not module:
        raise ValidationException("缺少 module 参数")
    data = load_yaml()
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get(module), dict):
        data[module] = {}
    data[module]["enabled"] = bool(enable)
    save_yaml(data)
    reload_config_manager()
    return {"module": module, "enabled": bool(enable)}


def _update_ai_platforms(model_config: Any) -> None:
    if not isinstance(model_config, dict) or not isinstance(model_config.get("ai_platforms"), list):
        raise ValidationException("AI平台列表必须是对象数组")
    if any(not isinstance(platform, dict) for platform in model_config["ai_platforms"]):
        raise ValidationException("AI平台列表必须是对象数组")
    try:
        current = get_ai_model_config()
        current["ai_platforms"] = model_config["ai_platforms"]
        save_ai_model_config(current)
    except (OSError, ValueError, yaml.YAMLError) as e:
        raise ConfigException(f"AI平台配置保存失败: {e}") from e


def update_plugin(name: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """保存插件配置，兼容 key-value 与 items 两种提交方式。"""
    if name == "miku_ai":
        config_values = body.get("config", {})
        item_values = body.get("items", [])
        legacy_keys = set(config_values) & set(AI_MODEL_CONFIG_KEYS) if isinstance(config_values, dict) else set()
        if isinstance(item_values, list):
            legacy_keys.update(
                item.get("key")
                for item in item_values
                if isinstance(item, dict) and item.get("key") in AI_MODEL_CONFIG_KEYS
            )
        if legacy_keys:
            raise ValidationException("AI 模型连接配置已独立，请到「配置编辑 - 全局 AI 模型」中修改")

        if "ai_model_config" in body:
            _update_ai_platforms(body["ai_model_config"])
            if not any(key in body for key in ("enabled", "config", "items", "special_users")):
                logger.success("[WebUI] 全局 AI 平台列表已热更新")
                return {"updated": True}

    data = load_yaml()
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get(name), dict):
        data[name] = {"enabled": True}

    if "enabled" in body:
        data[name]["enabled"] = bool(body["enabled"])
    if isinstance(body.get("config"), dict):
        data[name].update(body["config"])
    if "special_users" in body:
        special_users = body["special_users"]
        if not isinstance(special_users, list) or any(not isinstance(u, dict) for u in special_users):
            raise ValidationException("特殊人物列表必须是对象数组")
        data[name]["special_users"] = special_users
    if isinstance(body.get("items"), list):
        for item in body["items"]:
            if not isinstance(item, dict) or "key" not in item:
                continue
            key = item["key"]
            if key == "special_users":
                continue
            value = item.get("value", "")
            if str(value).strip() == "" and key != "enabled":
                continue
            data[name][key] = input_to_value(value)

    save_yaml(data)
    try:
        migrate_legacy_ai_config()
    except (OSError, ValueError, yaml.YAMLError) as e:
        raise ConfigException(f"清理旧版 AI 模型配置失败: {e}") from e
    reload_config_manager()
    logger.success(f"[WebUI] 插件 {name} 配置已热更新")
    return {"updated": True}


def get_plugin_config_items(module: str) -> Dict[str, Any]:
    """简化版插件配置（v1 风格）。"""
    config = load_yaml()
    plugin_config = config.get(module, {}) if isinstance(config, dict) else {}
    items = []
    if isinstance(plugin_config, dict):
        for key, value in plugin_config.items():
            if key == "enabled":
                continue
            items.append({"key": key, "value": value, "type": type(value).__name__})
    return {"module": module, "config": items}


def find_plugin(name: str) -> Optional[Dict[str, Any]]:
    return next((p for p in get_plugin_list() if p["name"] == name), None)
