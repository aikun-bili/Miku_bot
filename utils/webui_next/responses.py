"""统一响应结构。

所有 WebUI 接口都以 ``APIResponse`` 返回：
``{"success": bool, "message": str, "code": int, "data": Any}``

为了兼容旧版前端（``/api/*`` 直接读取 data 字段），
``routers/main.py`` 中的兼容中间件会为 ``/api/*`` 自动拆包。
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应模型。"""

    success: bool = True
    message: str = "ok"
    code: int = 200
    data: Optional[T] = None


def ok(data: Any = None, message: str = "ok", code: int = 200) -> dict:
    """构造成功响应。"""
    return APIResponse[Any](success=True, message=message, code=code, data=data).model_dump()


def created(data: Any = None, message: str = "创建成功") -> dict:
    return ok(data, message=message, code=201)


def fail(message: str = "请求失败", code: int = 400, data: Any = None) -> dict:
    """构造失败响应。"""
    return APIResponse[Any](success=False, message=message, code=code, data=data).model_dump()
