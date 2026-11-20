"""数据库路由：表结构、分页数据与 SQL 执行。"""

from fastapi import APIRouter, Request

from .. import database
from ..exceptions import ValidationException
from ..responses import ok

router = APIRouter(tags=["database"])


@router.get("/database/tables", summary="表列表")
async def tables():
    return ok({"tables": database.list_tables()})


@router.get("/database/tables/{table_name}/columns", summary="表字段")
async def table_columns(table_name: str):
    return ok({"columns": database.table_columns(table_name)})


@router.get("/database/tables/{table_name}/data", summary="表数据")
async def table_data(table_name: str, page: int = 1, page_size: int = 50):
    return ok(database.table_data(table_name, page, page_size))


@router.post("/database/execute", summary="执行 SQL")
async def execute_sql(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationException("请求格式错误") from e
    sql = str(body.get("sql", ""))
    return ok(database.execute(sql))
