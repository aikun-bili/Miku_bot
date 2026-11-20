"""安全路径校验：所有文件操作必须限制在项目根目录内。"""

from pathlib import Path

from .exceptions import FileException, PermissionException
from .paths import BASE_DIR


def resolve_in_base(relative_path: str) -> Path:
    """把相对路径解析为项目内的绝对路径，越界直接抛异常。"""
    raw = (relative_path or "").strip().replace("\\", "/")
    if ".." in Path(raw).parts:
        raise PermissionException("路径越界")
    target = (BASE_DIR / raw).resolve()
    if target != BASE_DIR and BASE_DIR not in target.parents:
        raise PermissionException("路径越界")
    return target


def to_relative(path: Path) -> str:
    """把绝对路径转成项目内的相对路径（统一使用 /）。"""
    try:
        return str(path.resolve().relative_to(BASE_DIR)).replace("\\", "/")
    except ValueError as e:
        raise PermissionException("路径越界") from e


def ensure_file(relative_path: str) -> Path:
    target = resolve_in_base(relative_path)
    if not target.exists() or not target.is_file():
        raise FileException("文件不存在")
    return target


def ensure_dir(relative_path: str) -> Path:
    target = resolve_in_base(relative_path)
    if not target.exists() or not target.is_dir():
        raise FileException("目录不存在")
    return target


def ensure_parent_dir(relative_path: str) -> Path:
    target = resolve_in_base(relative_path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise FileException(f"创建目录失败: {e}") from e
    return target
