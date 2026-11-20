"""数据库访问层（SQLite）。

WebUI 的数据库页会聚合 ``data/*.db``：
- 表名以 ``<库名>.<表名>`` 展示，如 ``ai_chat_history.messages``；
- 连接默认库（miku.db）时把其余库 ``ATTACH`` 为 schema，便于跨库查询；
- 表名统一做白名单校验，避免 SQL 注入。
"""

import re
import sqlite3
from typing import Any, Dict, List, Tuple

from .exceptions import NotFoundException, ValidationException
from .paths import DATA_DIR

DEFAULT_DB = DATA_DIR / "miku.db"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALIAS_RE = re.compile(r"\bmiku\.", re.IGNORECASE)


def _db_files() -> List[Tuple[str, Any]]:
    """返回 (别名, 路径)，别名取文件名去后缀。"""
    files = []
    if DATA_DIR.exists():
        for path in sorted(DATA_DIR.glob("*.db")):
            alias = path.stem.replace(".", "_")
            if _IDENTIFIER.match(alias):
                files.append((alias, path))
    return files


def _check_identifier(name: str) -> str:
    if not name or not _IDENTIFIER.match(name):
        raise ValidationException("非法的表名")
    return name


def _resolve(table: str) -> Tuple[str, str, Any]:
    """把 ``库名.表名`` 解析为 (schema, 表名, 库路径)。"""
    if "." in table:
        alias, name = table.split(".", 1)
    else:
        alias, name = "miku", table
    alias = _check_identifier(alias)
    name = _check_identifier(name)
    for db_alias, path in _db_files():
        if db_alias == alias:
            schema = "main" if path == DEFAULT_DB else alias
            return schema, name, path
    raise NotFoundException("数据库不存在")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DEFAULT_DB))
    conn.row_factory = sqlite3.Row
    # 附加其余数据库，便于跨库查询
    for alias, path in _db_files():
        if path == DEFAULT_DB:
            continue
        try:
            conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(path),))
        except sqlite3.Error:
            pass
    return conn


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        return f"<blob {len(data)}B>"
    return value


def list_tables() -> List[str]:
    tables: List[str] = []
    for alias, path in _db_files():
        if not path.exists():
            continue
        try:
            conn = sqlite3.connect(str(path))
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            tables.extend(f"{alias}.{row[0]}" for row in rows)
            conn.close()
        except sqlite3.Error:
            continue
    return tables


def table_columns(table: str) -> List[Dict[str, Any]]:
    schema, name, path = _resolve(table)
    with connect() as conn:
        rows = conn.execute(f'PRAGMA {schema}.table_info("{name}")').fetchall()
    if not rows:
        raise NotFoundException("数据表不存在")
    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": row["notnull"],
            "default": row["dflt_value"],
            "pk": row["pk"],
        }
        for row in rows
    ]


def table_data(table: str, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    schema, name, path = _resolve(table)
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))
    qualified = f'"{schema}"."{name}"'
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM {qualified} LIMIT ? OFFSET ?", (page_size, offset)
        ).fetchall()
    return {
        "table": table,
        "columns": [d[0] for d in (rows[0].keys() if rows else [])],
        "data": [{key: _jsonable(value) for key, value in dict(row).items()} for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


def execute(sql: str, params: Any = None) -> Dict[str, Any]:
    """执行 SQL（仅允许单条语句）。"""
    statement = (sql or "").strip().rstrip(";")
    if not statement:
        raise ValidationException("SQL 不能为空")
    if ";" in statement:
        raise ValidationException("只允许执行单条 SQL")
    # 默认库在连接里是 main，这里兼容 ``miku.xxx`` 写法
    statement = _ALIAS_RE.sub("main.", statement)

    with connect() as conn:
        cursor = conn.execute(statement, params or ())
        if statement.lstrip().upper().startswith(("SELECT", "PRAGMA", "WITH")):
            rows = cursor.fetchall()
            return {
                "rows": [{key: _jsonable(value) for key, value in dict(row).items()} for row in rows],
                "columns": [d[0] for d in (cursor.description or [])],
                "rowcount": len(rows),
            }
        conn.commit()
        return {"rowcount": cursor.rowcount}
