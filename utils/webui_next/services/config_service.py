"""配置服务：读取 / 写入 bot.yaml、AI 模型配置、备份与恢复、黑名单。"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from nonebot.log import logger

from ..exceptions import ConfigException
from ..paths import BACKUP_DIR, BLACKLIST_FILE, CONFIG_FILE
from utils.ai_model_config import (
    AI_MODEL_CONFIG_FILE,
    default_ai_model_config_text,
    migrate_legacy_ai_config,
    migrate_local_model_to_platforms,
    parse_ai_model_config,
)

try:
    from utils.config_manager import config_manager as _config_manager
except Exception:  # pragma: no cover - 配置管理器不可用时降级
    _config_manager = None


def load_yaml() -> Dict[str, Any]:
    """读取 bot.yaml，失败时返回空字典。"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"[WebUI] 读取 bot.yaml 失败: {e}")
        return {}


def save_yaml(data: Dict[str, Any]) -> None:
    try:
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    except OSError as e:
        raise ConfigException(f"写入配置失败: {e}") from e


def reload_config_manager() -> None:
    if _config_manager is None:
        return
    try:
        _config_manager.reload()
    except Exception as e:  # pragma: no cover - 热更新失败不影响主流程
        logger.warning(f"[WebUI] 热更新 config_manager 失败: {e}")


def config_file_for(target: str) -> Path:
    if target == "bot":
        return CONFIG_FILE
    if target == "ai-models":
        return AI_MODEL_CONFIG_FILE
    raise ConfigException("未知配置文件")


def create_backup(target: str = "bot") -> Optional[str]:
    config_file = config_file_for(target)
    if not config_file.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = BACKUP_DIR / f"{config_file.name}.{timestamp}"
    try:
        shutil.copy2(config_file, backup_path)
    except OSError as e:
        raise ConfigException(f"创建备份失败: {e}") from e
    return timestamp


def list_backups(target: str = "bot") -> List[Dict[str, Any]]:
    backups: List[Dict[str, Any]] = []
    try:
        config_file = config_file_for(target)
        prefix = f"{config_file.name}."
        for f in sorted(BACKUP_DIR.glob(f"{prefix}*"), reverse=True)[:20]:
            backups.append({"timestamp": f.name.removeprefix(prefix), "size": f.stat().st_size})
    except (OSError, ConfigException):
        pass
    return backups


def read_config(target: str = "bot") -> Dict[str, Any]:
    config_file = config_file_for(target)
    content = ""
    if config_file.exists():
        try:
            content = config_file.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigException(f"读取配置失败: {e}") from e
    elif target == "ai-models":
        content = default_ai_model_config_text()
    return {"content": content, "target": target, "backups": list_backups(target)}


def _validate_content(target: str, content: str) -> None:
    if target == "ai-models":
        try:
            parse_ai_model_config(content)
        except ValueError as e:
            raise ConfigException(str(e)) from e
        return
    try:
        if content.strip():
            yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ConfigException(f"YAML 格式错误: {e}") from e


def update_config(content: str, target: str = "bot") -> Dict[str, Any]:
    if not isinstance(content, str):
        raise ConfigException("配置内容必须是字符串")
    config_file = config_file_for(target)
    _validate_content(target, content)

    create_backup(target)
    try:
        config_file.write_text(content, encoding="utf-8")
    except OSError as e:
        raise ConfigException(f"写入配置失败: {e}") from e

    if target == "bot":
        try:
            migrate_legacy_ai_config()
        except (OSError, ValueError, yaml.YAMLError) as e:
            raise ConfigException(f"迁移旧版 AI 模型配置失败: {e}") from e
        reload_config_manager()
        logger.success("[WebUI] 主配置已热更新")
    else:
        try:
            migrate_local_model_to_platforms()
        except Exception as e:  # pragma: no cover
            logger.warning(f"[WebUI] 本地模型迁移失败: {e}")
        logger.success("[WebUI] 全局 AI 模型配置已热更新")
    return {"target": target}


def restore_backup(timestamp: str, target: str = "bot") -> Dict[str, Any]:
    config_file = config_file_for(target)
    backup_path = BACKUP_DIR / f"{config_file.name}.{timestamp}"
    if not backup_path.exists():
        raise ConfigException("备份不存在")

    if target == "ai-models":
        try:
            parse_ai_model_config(backup_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ConfigException(f"AI 模型配置备份无效: {e}") from e

    create_backup(target)
    try:
        shutil.copy2(backup_path, config_file)
    except OSError as e:
        raise ConfigException(f"恢复备份失败: {e}") from e

    if target == "bot":
        try:
            migrate_legacy_ai_config()
        except (OSError, ValueError, yaml.YAMLError) as e:
            raise ConfigException(f"迁移旧版 AI 模型配置失败: {e}") from e
        reload_config_manager()
        logger.success(f"[WebUI] 已从备份恢复并热更新配置（{timestamp}）")
    else:
        try:
            migrate_local_model_to_platforms()
        except Exception as e:  # pragma: no cover
            logger.warning(f"[WebUI] 恢复备份后本地模型迁移失败: {e}")
        logger.success(f"[WebUI] 已恢复全局 AI 模型配置（{timestamp}）")
    return {"target": target, "timestamp": timestamp}


# ===================== 黑名单 =====================
def load_blacklist() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if BLACKLIST_FILE.exists():
        try:
            data = json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("global_disabled", [])
    data.setdefault("group_disabled", {})
    data.setdefault("user_disabled", {})
    return data


def save_blacklist(data: Dict[str, Any]) -> None:
    try:
        BLACKLIST_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        raise ConfigException(f"保存黑名单失败: {e}") from e


def add_blacklist_item(scope: str, target_id: str, plugin: str) -> Dict[str, Any]:
    if scope not in ("group", "user"):
        raise ConfigException("未知黑名单类型")
    if not plugin:
        raise ConfigException("缺少 plugin 参数")
    key = f"{scope}_disabled"
    data = load_blacklist()
    data.setdefault(key, {})
    data[key].setdefault(target_id, [])
    if plugin not in data[key][target_id]:
        data[key][target_id].append(plugin)
    save_blacklist(data)
    return data


def remove_blacklist_item(scope: str, target_id: str, plugin: str) -> Dict[str, Any]:
    if scope not in ("group", "user"):
        raise ConfigException("未知黑名单类型")
    key = f"{scope}_disabled"
    data = load_blacklist()
    if target_id in data.get(key, {}):
        data[key][target_id] = [p for p in data[key][target_id] if p != plugin]
        if not data[key][target_id]:
            del data[key][target_id]
    save_blacklist(data)
    return data


# ===================== 表单值转换 =====================
def value_to_input(value: Any) -> str:
    if isinstance(value, list):
        if any(isinstance(item, dict) for item in value):
            return json.dumps(value, ensure_ascii=False, indent=2)
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item.replace("\n", "").strip())
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def input_to_value(raw: Any) -> Any:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return ""
    # 前端配置弹窗会把 list/dict 序列化为 JSON 字符串
    if text.startswith(("[", "{")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    if "\n" in text:
        return [line.strip() for line in text.split("\n") if line.strip()]
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return text
