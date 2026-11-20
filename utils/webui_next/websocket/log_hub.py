"""日志推送中心：把运行日志实时分发给 WebSocket 订阅者。

NoneBot2 使用 loguru，因此同时挂两类采集：
- loguru sink（主要来源，``nonebot.log.logger``）
- 标准 logging handler（兜底捕获第三方库写到 ``logging.getLogger("nonebot")`` 的记录）
"""

import asyncio
import logging
import re
import threading
from collections import deque
from typing import Deque, List, Optional, Set

# 心跳类日志不推送，避免刷屏
IGNORE_KEYWORDS = ("heartbeat", "心跳", "websocket ping")
_LEVEL_RE = re.compile(r"\[(TRACE|DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\]", re.IGNORECASE)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
BACKLOG_SIZE = 200


def detect_level(text: str) -> str:
    match = _LEVEL_RE.search(text)
    return match.group(1).lower() if match else "info"


def _clean(text: str) -> Optional[str]:
    message = _ANSI_RE.sub("", str(text)).rstrip()
    if not message:
        return None
    lowered = message.lower()
    if any(keyword in lowered for keyword in IGNORE_KEYWORDS):
        return None
    return message


class LogHub:
    """线程安全的日志广播中心。"""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        self._installed = False
        self._backlog: Deque[str] = deque(maxlen=BACKLOG_SIZE)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def history(self) -> List[str]:
        with self._lock:
            return list(self._backlog)

    def publish(self, text: str) -> None:
        message = _clean(text)
        if not message:
            return
        with self._lock:
            self._backlog.append(message)
            subscribers = list(self._subscribers)
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for queue in subscribers:
            try:
                loop.call_soon_threadsafe(self._push, queue, message)
            except RuntimeError:
                pass

    @staticmethod
    def _push(queue: asyncio.Queue, text: str) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(text)
        except asyncio.QueueFull:
            pass

    def install(self, logger_name: str = "nonebot") -> None:
        if self._installed:
            return
        self._installed = True

        handler = _HubHandler(self)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        std_logger = logging.getLogger(logger_name)
        if not any(isinstance(h, _HubHandler) for h in std_logger.handlers):
            std_logger.addHandler(handler)

        # NoneBot 的实际日志走 loguru，必须单独挂 sink
        try:
            from nonebot.log import logger as nb_logger

            nb_logger.add(
                _loguru_sink,
                level="INFO",
                format="[{level}] {message}",
                colorize=False,
                enqueue=False,
            )
        except Exception:  # pragma: no cover - loguru 不可用时退回 logging
            pass


class _HubHandler(logging.Handler):
    def __init__(self, hub: LogHub) -> None:
        super().__init__()
        self.hub = hub

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.hub.publish(self.format(record))
        except Exception:
            return


def _loguru_sink(message) -> None:
    hub.publish(str(message))


hub = LogHub()
