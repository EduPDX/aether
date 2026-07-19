"""Rotas de catálogo: buscar, ver versões, instalar e checar atualizações."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from aether_core.interfaces.http.deps import (
    ContentRead,
    ContentWrite,
    InstanceServiceDep,
    SourceServiceDep,
)

router = APIRouter(prefix="/instances/{instance_id}/sources", tags=["sources"])


class InstallRequest(BaseModel):
    source_id: str
    version_id: str
    type: str = "mod"
    overwrite: bool = False


def _item(i) -> dict:
    return {
        "source_id": i.source_id,
        "project_id": i.project_id,
        "slug": i.slug,
        "name": i.name,
        "summary": i.summary,
        "author": i.author,
        "downloads": i.downloads,
        "icon_url": i.icon_url,
        "page_url": i.page_url,
        "categories": list(i.categories),
    }


def _version(v) -> dict:
    return {
        "source_id": v.source_id,
        "project_id": v.project_id,
        "version_id": v.version_id,
        "version_number": v.version_number,
        "file_name": v.file_name,
        "size": v.size,
        "game_versions": list(v.game_versions),
        "loaders": list(v.loaders),
        "released_at": v.released_at.isoformat() if v.released_at else None,
        "dependencies": [{"project_id": d.project_id, "kind": d.kind} for d in v.dependencies],
    }


@router.get("")
async def list_sources(
    instance_id: str,
    instances: InstanceServiceDep,
    sources: SourceServiceDep,
    _: ContentRead,
) -> list[dict]:
    instance = await instances.get(instance_id)
    return [
        {"id": s.id, "label": s.label, "requires_api_key": s.requires_api_key}
        for s in sources.sources(instance)
    ]


@router.get("/search")
async def search(
    instance_id: str,
    q: str,
    instances: InstanceServiceDep,
    sources: SourceServiceDep,
    _: ContentRead,
    source_id: str = "modrinth",
    limit: int = 20,
    offset: int = 0,
    all_versions: bool = False,
) -> list[dict]:
    instance = await instances.get(instance_id)
    itens = await sources.search(
        instance,
        source_id,
        q,
        limit=min(limit, 50),
        offset=offset,
        filter_by_game=not all_versions,
    )
    return [_item(i) for i in itens]


@router.get("/versions")
async def versions(
    instance_id: str,
    project_id: str,
    instances: InstanceServiceDep,
    sources: SourceServiceDep,
    _: ContentRead,
    source_id: str = "modrinth",
    all_versions: bool = False,
) -> list[dict]:
    instance = await instances.get(instance_id)
    lista = await sources.versions(
        instance, source_id, project_id, filter_by_game=not all_versions
    )
    return [_version(v) for v in lista]


@router.post("/install", status_code=201)
async def install(
    instance_id: str,
    body: InstallRequest,
    request: Request,
    instances: InstanceServiceDep,
    sources: SourceServiceDep,
    user: ContentWrite,
) -> dict:
    instance = await instances.get(instance_id)
    resultado = await sources.install_by_id(
        instance, body.type, body.source_id, body.version_id, overwrite=body.overwrite
    )
    await _audit(
        request,
        f"content.install instance={instance.name} file={resultado['file']} "
        f"source={body.source_id}",
        user,
    )
    return resultado


@router.get("/updates")
async def updates(
    instance_id: str,
    instances: InstanceServiceDep,
    sources: SourceServiceDep,
    _: ContentRead,
    source_id: str = "modrinth",
    type: str = "mod",
) -> list[dict]:
    """Mods instalados que têm versão mais nova.

    Pode demorar em instalações grandes: identifica cada arquivo por hash
    antes de consultar o catálogo.
    """
    instance = await instances.get(instance_id)
    candidatos = await sources.check_updates(instance, type, source_id)
    return [c.__dict__ for c in candidatos]


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
