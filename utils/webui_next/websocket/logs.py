"""WebSocket：实时日志推送。"""

import asyncio
import time

from fastapi import WebSocket, WebSocketDisconnect
from nonebot.log import logger

from .log_hub import detect_level, hub

HEARTBEAT_INTERVAL = 20


async def logs_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = hub.subscribe()
    try:
        await websocket.send_json(
            {"type": "connected", "timestamp": int(time.time() * 1000), "message": "日志推送已连接"}
        )
        # 先补发最近日志，避免页面打开后空白
        for message in hub.history():
            await websocket.send_json(
                {
                    "type": "log",
                    "level": detect_level(message),
                    "message": message,
                    "module": "nonebot",
                    "timestamp": int(time.time() * 1000),
                }
            )
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {"type": "heartbeat", "timestamp": int(time.time() * 1000)}
                )
                continue
            await websocket.send_json(
                {
                    "type": "log",
                    "level": detect_level(message),
                    "message": message,
                    "module": "nonebot",
                    "timestamp": int(time.time() * 1000),
                }
            )
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception as e:  # pragma: no cover - 客户端异常断开
        logger.debug(f"[WebUI] 日志 WebSocket 断开: {e}")
    finally:
        hub.unsubscribe(queue)
