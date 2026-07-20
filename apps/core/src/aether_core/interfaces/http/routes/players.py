"""Rotas de jogadores: ler as listas de acesso e alterá-las."""

from aether_sdk import PlayerAction
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aether_core.interfaces.http.deps import (
    InstanceServiceDep,
    InstancesRead,
    PlayerServiceDep,
    PowerUse,
)

router = APIRouter(tags=["players"])


class PlayerEntryOut(BaseModel):
    name: str
    id: str
    detail: str


class PlayerListOut(BaseModel):
    kind: str
    label: str
    enforced: bool
    entries: list[PlayerEntryOut]


class ActionRequest(BaseModel):
    action: PlayerAction
    name: str = Field(min_length=1, max_length=32)
    reason: str = Field(default="", max_length=200)


@router.get("/instances/{instance_id}/players")
async def list_players(
    instance_id: str,
    instances: InstanceServiceDep,
    players: PlayerServiceDep,
    _: InstancesRead,
) -> dict:
    instance = await instances.get(instance_id)
    listas = players.lists(instance)
    return {
        "lists": [
            PlayerListOut(
                kind=str(le.kind),
                label=le.label,
                enforced=le.enforced,
                entries=[PlayerEntryOut(name=e.name, id=e.id, detail=e.detail) for e in le.entries],
            )
            for le in listas
        ]
    }


@router.post("/instances/{instance_id}/players/action")
async def apply_action(
    instance_id: str,
    body: ActionRequest,
    request: Request,
    instances: InstanceServiceDep,
    players: PlayerServiceDep,
    user: PowerUse,
) -> dict:
    instance = await instances.get(instance_id)
    via = await players.apply(instance, body.action, body.name, body.reason)
    await _audit(
        request,
        f"players.{body.action} instance={instance.name} player={body.name} via={via}",
        user,
    )
    return {"applied_via": via}


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
