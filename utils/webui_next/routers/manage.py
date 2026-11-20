"""管理路由：群组、好友、申请与聊天。"""

from fastapi import APIRouter, Request

from ..exceptions import ValidationException
from ..responses import ok
from ..services import manage_service

router = APIRouter(tags=["manage"])


@router.get("/groups", summary="群列表")
async def groups():
    return ok(await manage_service.fetch_groups())


@router.get("/users", summary="好友列表")
async def users():
    return ok(await manage_service.fetch_users())


@router.get("/requests", summary="待处理申请")
async def requests():
    return ok(await manage_service.fetch_requests())


@router.post("/requests/{req_id}/approve", summary="同意申请")
async def approve(req_id: int):
    return ok(await manage_service.approve_request(req_id), "已同意")


@router.post("/requests/{req_id}/reject", summary="拒绝申请")
async def reject(req_id: int, request: Request):
    reason = ""
    try:
        body = await request.json()
        reason = str(body.get("reason", ""))
    except Exception:
        pass
    return ok(await manage_service.reject_request(req_id, reason), "已拒绝")


@router.post("/chat/send", summary="发送消息")
async def chat_send(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationException("参数错误") from e
    return ok(
        await manage_service.send_message(
            str(body.get("type", "private")),
            str(body.get("target_id", "")),
            str(body.get("message", "")),
        ),
        "发送成功",
    )


@router.get("/chat/history", summary="聊天记录")
async def chat_history(type: str = "private", target_id: str = "", limit: int = 100):
    return ok(manage_service.get_chat_history(type, target_id, limit))
