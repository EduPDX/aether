"""Rotas da lixeira: listar, restaurar, apagar de vez e esvaziar."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from aether_core.interfaces.http.deps import (
    FilesRead,
    FilesWrite,
    InstanceServiceDep,
    TrashServiceDep,
)

router = APIRouter(tags=["trash"])


class TrashItemOut(BaseModel):
    id: str
    name: str
    original_path: str
    is_dir: bool
    size_bytes: int
    origin: str
    content_type: str
    trashed_at: str


def _out(i) -> TrashItemOut:
    return TrashItemOut(
        id=i.id,
        name=i.name,
        original_path=i.original_path,
        is_dir=i.is_dir,
        size_bytes=i.size_bytes,
        origin=str(i.origin),
        content_type=i.content_type,
        trashed_at=i.trashed_at.isoformat(),
    )


@router.get("/instances/{instance_id}/trash")
async def list_trash(
    instance_id: str,
    instances: InstanceServiceDep,
    trash: TrashServiceDep,
    _: FilesRead,
) -> dict:
    instance = await instances.get(instance_id)
    itens = await trash.list(instance)
    return {
        "items": [_out(i) for i in itens],
        "total_bytes": sum(i.size_bytes for i in itens),
    }


@router.post("/instances/{instance_id}/trash/{item_id}/restore")
async def restore_item(
    instance_id: str,
    item_id: str,
    request: Request,
    instances: InstanceServiceDep,
    trash: TrashServiceDep,
    user: FilesWrite,
) -> dict:
    instance = await instances.get(instance_id)
    caminho = await trash.restore(instance, item_id)
    await _audit(request, f"trash.restore instance={instance.name} path={caminho}", user)
    return {"restored_to": caminho}


@router.delete("/instances/{instance_id}/trash/{item_id}", status_code=204)
async def purge_item(
    instance_id: str,
    item_id: str,
    request: Request,
    instances: InstanceServiceDep,
    trash: TrashServiceDep,
    user: FilesWrite,
) -> None:
    instance = await instances.get(instance_id)
    await trash.purge(instance, item_id)
    await _audit(request, f"trash.purge instance={instance.name} item={item_id}", user)


@router.delete("/instances/{instance_id}/trash", status_code=200)
async def empty_trash(
    instance_id: str,
    request: Request,
    instances: InstanceServiceDep,
    trash: TrashServiceDep,
    user: FilesWrite,
) -> dict:
    instance = await instances.get(instance_id)
    quantos = await trash.empty(instance)
    await _audit(request, f"trash.empty instance={instance.name} count={quantos}", user)
    return {"removed": quantos}


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
