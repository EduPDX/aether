"""Eventos autenticados, com permissões verificadas também antes do envio."""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from aether_core.application.auth import AuthService
from aether_core.domain.errors import AuthenticationError
from aether_core.domain.users import User
from aether_core.infrastructure.repositories import SqlUserRepository
from aether_core.interfaces.http.deps import _Hasher, _Tokens

router = APIRouter()

_PERMISSIONS = {
    "instance": "instances.read",
    "content": "content.read",
    "config": "config.read",
    "files": "files.read",
    "trash": "files.read",
    "sync": "sync.read",
    "backup": "backups.read",
    "players": "console.use",
    "task": "power.use",
    "images": "instances.write",
    "update": "users.manage",
}


def allowed(user: User, topic: str) -> bool:
    permission = _PERMISSIONS.get(topic.split(".", 1)[0])
    return permission is not None and user.has_permission(permission)


def matches(topic: str, prefix: str) -> bool:
    return topic == prefix or topic.startswith(prefix + ".")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    token = ws.query_params.get("token", "")

    async def authenticate() -> User:
        async with ws.app.state.session_factory() as session:
            return await AuthService(
                SqlUserRepository(session), _Hasher(), _Tokens(ws.app.state.jwt_secret)
            ).authenticate(token)

    try:
        await authenticate()
    except AuthenticationError:
        await ws.close(code=4401, reason="sessão inválida")
        return

    bus = ws.app.state.bus
    topics: set[str] = set()
    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=1000)

    def handler(topic: str, payload: dict[str, Any]) -> None:
        if any(matches(topic, prefix) for prefix in topics):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait((topic, payload))

    async def sender() -> None:
        seq = 0
        while True:
            try:
                topic, payload = await asyncio.wait_for(queue.get(), timeout=30)
            except TimeoutError:
                # Mesmo uma conexão ociosa não conserva sessão expirada.
                await authenticate()
                continue
            user = await authenticate()
            if not allowed(user, topic):
                continue
            seq += 1
            await ws.send_json(
                {
                    "topic": topic,
                    "payload": payload,
                    "ts": datetime.now(UTC).isoformat(),
                    "seq": seq,
                }
            )

    async def receiver() -> None:
        while True:
            msg = await ws.receive_json()
            if not isinstance(msg, dict):
                await ws.close(code=4400, reason="mensagem inválida")
                return
            op, topic = msg.get("op"), msg.get("topic", "")
            if not isinstance(topic, str) or not topic or len(topic) > 200:
                await ws.close(code=4400, reason="tópico inválido")
                return
            if op == "subscribe":
                if not allowed(await authenticate(), topic):
                    await ws.close(code=4403, reason="tópico não autorizado")
                    return
                if len(topics) >= 100 and topic not in topics:
                    await ws.close(code=4400, reason="limite de inscrições")
                    return
                topics.add(topic)
            elif op == "unsubscribe":
                topics.discard(topic)

    bus.subscribe("", handler)
    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except AuthenticationError:
        await ws.close(code=4401, reason="sessão inválida")
    except WebSocketDisconnect:
        pass
    except ValueError:
        await ws.close(code=4400, reason="mensagem inválida")
    finally:
        bus.unsubscribe(handler)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
