"""WebSocket endpoint: one socket, many topics.

Client → server: ``{"op": "subscribe"|"unsubscribe", "topic": "..."}``
Server → client: ``{"topic": ..., "payload": {...}, "ts": ..., "seq": n}``

Every message published on the internal event bus whose topic matches a
subscription is forwarded. Topics use prefix matching (subscribing to
``instance.abc`` receives ``instance.abc.console`` and ``.state``).
"""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    from aether_core.domain.errors import AuthenticationError
    from aether_core.infrastructure.repositories import SqlUserRepository
    from aether_core.infrastructure.security import decode_token

    await ws.accept()

    # Authenticate before serving any events (token via query param — the
    # browser WebSocket API cannot send headers).
    token = ws.query_params.get("token", "")
    try:
        user_id = decode_token(ws.app.state.jwt_secret, token, "access")
        async with ws.app.state.session_factory() as session:
            if await SqlUserRepository(session).get(user_id) is None:
                raise AuthenticationError("user no longer exists")
    except AuthenticationError:
        await ws.close(code=4401, reason="unauthorized")
        return

    bus = ws.app.state.bus
    topics: set[str] = set()
    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=1000)

    def handler(topic: str, payload: dict[str, Any]) -> None:
        if any(topic.startswith(t) for t in topics):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait((topic, payload))

    bus.subscribe("", handler)
    seq = 0

    async def sender() -> None:
        nonlocal seq
        while True:
            topic, payload = await queue.get()
            seq += 1
            await ws.send_json(
                {
                    "topic": topic,
                    "payload": payload,
                    "ts": datetime.now(UTC).isoformat(),
                    "seq": seq,
                }
            )

    send_task = asyncio.create_task(sender())
    try:
        while True:
            msg = await ws.receive_json()
            op, topic = msg.get("op"), msg.get("topic", "")
            if op == "subscribe" and topic:
                topics.add(topic)
            elif op == "unsubscribe":
                topics.discard(topic)
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        bus.unsubscribe(handler)
