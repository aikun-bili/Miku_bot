"""统一异常体系与全局异常处理。

自定义异常统一继承 ``APIException``，由全局处理器转换为 ``APIResponse``，
避免把 Python 异常堆栈直接暴露给前端。
"""

from typing import Any, Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from nonebot.log import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from .responses import fail


class APIException(Exception):
    """业务异常基类。"""

    status_code: int = 500
    code: int = 500
    message: str = "服务器内部错误"

    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[int] = None,
        status_code: Optional[int] = None,
        data: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or status_code or self.code
        self.status_code = status_code or code or self.status_code
        self.data = data
        super().__init__(self.message)


class ValidationException(APIException):
    status_code = 400
    code = 400
    message = "参数验证失败"


class AuthenticationException(APIException):
    status_code = 401
    code = 401
    message = "未登录或登录已过期"


class PermissionException(APIException):
    status_code = 403
    code = 403
    message = "权限不足"


class NotFoundException(APIException):
    status_code = 404
    code = 404
    message = "资源不存在"


class FileException(APIException):
    status_code = 400
    code = 400
    message = "文件操作失败"


class ConfigException(APIException):
    status_code = 400
    code = 400
    message = "配置操作失败"


class SystemException(APIException):
    status_code = 500
    code = 500
    message = "系统错误"


def _json(payload: dict, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    """把异常处理器注册到 FastAPI 应用上。"""

    @app.exception_handler(APIException)
    async def _api_exception_handler(_request, exc: APIException):
        return _json(fail(exc.message, code=exc.code, data=exc.data), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            details.append(f"{loc}: {err.get('msg', '')}".strip(": "))
        message = "参数验证失败"
        if details:
            message = f"{message}（{'; '.join(details[:3])}）"
        return _json(fail(message, code=400), 400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(_request, exc: StarletteHTTPException):
        return _json(
            fail(str(exc.detail), code=exc.status_code),
            exc.status_code,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_request, exc: Exception):
        logger.opt(exception=exc).error("[WebUI] 未捕获异常")
        return _json(fail("服务器内部错误", code=500), 500)
