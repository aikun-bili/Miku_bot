"""文件路由：浏览、读取、保存、删除、重命名与创建。"""

from fastapi import APIRouter, Request

from ..exceptions import ValidationException
from ..responses import ok
from ..services import file_service

router = APIRouter(tags=["file"])


@router.get("/file/list", summary="目录列表")
async def file_list(path: str = ""):
    return ok(file_service.list_dir(path))


@router.get("/file/read", summary="读取文件")
async def file_read(file_path: str):
    return ok(file_service.read_file(file_path))


@router.post("/file/save", summary="保存文件")
async def file_save(request: Request):
    body = await _json(request)
    return ok(file_service.save_file(body.get("file_path", ""), body.get("content", "")), "已保存")


@router.post("/file/delete", summary="删除文件或目录")
async def file_delete(request: Request):
    body = await _json(request)
    return ok(file_service.delete_path(body.get("file_path", "")), "已删除")


@router.post("/file/delete-folder", summary="删除目录")
async def file_delete_folder(request: Request):
    body = await _json(request)
    return ok(file_service.delete_path(body.get("file_path", "")), "已删除")


@router.post("/file/rename", summary="重命名")
async def file_rename(request: Request):
    body = await _json(request)
    return ok(
        file_service.rename_path(body.get("source_path", ""), body.get("new_name", "")),
        "已重命名",
    )


@router.post("/file/create-file", summary="创建文件")
async def file_create(request: Request):
    body = await _json(request)
    return ok(file_service.create_file(body.get("parent_path", ""), body.get("name", "")), "已创建")


@router.post("/file/create-folder", summary="创建目录")
async def folder_create(request: Request):
    body = await _json(request)
    return ok(file_service.create_folder(body.get("parent_path", ""), body.get("name", "")), "已创建")


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    if not isinstance(body, dict):
        raise ValidationException("请求格式错误")
    return body
