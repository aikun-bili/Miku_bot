"""文件服务：项目内文件的浏览、读取、保存、删除与重命名。"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ..exceptions import FileException, ValidationException
from ..formatters import format_size
from ..path_validator import ensure_dir, ensure_file, ensure_parent_dir, resolve_in_base, to_relative
from ..paths import BASE_DIR


def _absolute_path(path: Path) -> str:
    return to_relative(path) if path != BASE_DIR else "."


def list_dir(path: str = "") -> Dict[str, Any]:
    target = resolve_in_base(path)
    if not target.exists() or not target.is_dir():
        raise FileException("目录不存在")

    items = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        try:
            stat = entry.stat()
        except OSError:
            continue
        items.append(
            {
                "name": entry.name,
                "path": to_relative(entry),
                "is_dir": entry.is_dir(),
                "size": stat.st_size if entry.is_file() else 0,
                "size_str": format_size(stat.st_size) if entry.is_file() else "-",
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    parent = None if target == BASE_DIR else _absolute_path(target.parent)
    return {"path": _absolute_path(target), "parent": parent, "items": items}


def read_file(file_path: str) -> Dict[str, Any]:
    target = ensure_file(file_path)
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise FileException("该文件不是 UTF-8 文本，无法在线预览") from e
    except OSError as e:
        raise FileException(f"读取失败: {e}") from e
    return {
        "path": to_relative(target),
        "content": content,
        "size": target.stat().st_size,
        "size_str": format_size(target.stat().st_size),
    }


def save_file(file_path: str, content: str) -> Dict[str, Any]:
    if not isinstance(content, str):
        raise ValidationException("文件内容必须是字符串")
    target = ensure_parent_dir(file_path)
    try:
        target.write_text(content, encoding="utf-8")
    except OSError as e:
        raise FileException(f"保存失败: {e}") from e
    return {"path": to_relative(target), "size": target.stat().st_size}


def delete_path(file_path: str) -> Dict[str, Any]:
    target = resolve_in_base(file_path)
    if target == BASE_DIR:
        raise FileException("不允许删除项目根目录")
    if not target.exists():
        raise FileException("文件不存在")

    import shutil

    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as e:
        raise FileException(f"删除失败: {e}") from e
    return {"path": file_path, "deleted": True}


def rename_path(source_path: str, new_name: str) -> Dict[str, Any]:
    if not new_name or "/" in new_name or "\\" in new_name or ".." in new_name:
        raise ValidationException("文件名不合法")
    source = resolve_in_base(source_path)
    if not source.exists():
        raise FileException("文件不存在")
    target = source.parent / new_name
    if target.exists():
        raise FileException("目标名称已存在")
    try:
        source.rename(target)
    except OSError as e:
        raise FileException(f"重命名失败: {e}") from e
    return {"path": to_relative(target)}


def create_file(parent_path: str, name: str) -> Dict[str, Any]:
    target = _prepare_new_path(parent_path, name, "文件")
    try:
        target.touch()
    except OSError as e:
        raise FileException(f"创建文件失败: {e}") from e
    return {"path": to_relative(target)}


def create_folder(parent_path: str, name: str) -> Dict[str, Any]:
    target = _prepare_new_path(parent_path, name, "文件夹")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise FileException(f"创建文件夹失败: {e}") from e
    return {"path": to_relative(target)}


def _prepare_new_path(parent_path: str, name: str, label: str) -> Path:
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ValidationException("名称不合法")
    parent = ensure_dir(parent_path)
    target = parent / name
    if target.exists():
        raise FileException(f"{label}已存在")
    return target
