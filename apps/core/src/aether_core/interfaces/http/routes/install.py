"""Rotas de versão do servidor: listar, consultar a instalada e atualizar."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from aether_core.interfaces.http.deps import (
    BackupServiceDep,
    InstanceServiceDep,
    InstancesRead,
    InstancesWrite,
)

router = APIRouter(tags=["versions"])


class InstallRequest(BaseModel):
    version: str
    skip_backup: bool = False
    """Pular o backup é decisão explícita de quem sabe o que está fazendo."""


@router.get("/providers/{provider_id}/versions")
async def provider_versions(request: Request, provider_id: str, _: InstancesRead) -> list[dict]:
    versoes = await request.app.state.installs.versions(provider_id)
    return [v.model_dump() for v in versoes]


@router.get("/instances/{instance_id}/version")
async def instance_version(
    request: Request, instance_id: str, svc: InstanceServiceDep, _: InstancesRead
) -> dict:
    instance = await svc.get(instance_id)
    installs = request.app.state.installs
    return {
        "installed": installs.installed_version(instance),
        "requested": (instance.provider_data.get("install") or {}).get("version", ""),
        "installing": installs.rodando(instance_id),
    }


@router.post("/instances/{instance_id}/install", status_code=202)
async def install(
    request: Request,
    instance_id: str,
    body: InstallRequest,
    svc: InstanceServiceDep,
    backups: BackupServiceDep,
    _: InstancesWrite,
) -> dict:
    """Dispara a instalação e devolve na hora (202).

    O backup acontece dentro do fluxo, antes de tocar em qualquer arquivo, e
    falha de backup cancela a atualização. O progresso sai pelo console da
    instância e pelo tópico ``instance.{id}.job``.
    """
    instance = await svc.get(instance_id)
    await request.app.state.installs.start(
        instance,
        body.version,
        backup_service=backups,
        skip_backup=body.skip_backup,
    )
    return {"version": body.version, "status": "started"}
