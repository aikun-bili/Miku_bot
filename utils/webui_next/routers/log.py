"""日志路由：文件列表、内容读取与尾部截取。"""

from fastapi import APIRouter

from ..responses import ok
from ..services import log_service

router = APIRouter(tags=["log"])


@router.get("/logs", summary="日志文件列表")
async def log_list():
    return ok({"files": log_service.list_log_files()})


@router.get("/logs/{filename}", summary="读取日志内容")
async def log_content(filename: str, max_lines: int = log_service.MAX_LOG_LINES):
    return ok(log_service.read_log_file(filename, max_lines))


@router.get("/logs/{filename}/tail", summary="读取日志尾部")
async def log_tail(filename: str, lines: int = 100):
    return ok(log_service.tail_log_file(filename, lines))


@router.get("/log/list", summary="日志文件列表（v1）")
async def log_list_v1():
    return ok({"files": log_service.list_log_files()})


@router.get("/log/content", summary="读取日志内容（v1）")
async def log_content_v1(filename: str = "", lines: int = 200):
    return ok(log_service.read_log_file(filename, lines))
