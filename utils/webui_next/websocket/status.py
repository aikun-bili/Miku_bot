"""WebSocket：每 5 秒推送一次设备状态。"""

import asyncio
import time

from fastapi import WebSocket, WebSocketDisconnect
from nonebot.log import logger

from ..services import system_service

PUSH_INTERVAL = 5


async def status_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            status = system_service.get_status()
            status.update(
                {
                    "type": "system_status",
                    "timestamp": int(time.time() * 1000),
                }
            )
            await websocket.send_json(status)
            await asyncio.sleep(PUSH_INTERVAL)
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception as e:  # pragma: no cover - 客户端异常断开
        logger.debug(f"[WebUI] 状态 WebSocket 断开: {e}")
