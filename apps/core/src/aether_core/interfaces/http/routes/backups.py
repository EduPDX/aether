"""Backup routes: listar, criar, baixar, restaurar, apagar e agendar."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from aether_core.domain.backups import BackupKind, BackupPolicy, BackupSchedule
from aether_core.interfaces.http.deps import (
    BackupServiceDep,
    BackupsRead,
    BackupsWrite,
    InstanceServiceDep,
)

router = APIRouter(tags=["backups"])


class BackupOut(BaseModel):
    id: str
    file_name: str
    size_bytes: int
    kind: str
    note: str
    created_at: str


class CreateBackupRequest(BaseModel):
    note: str = Field(default="", max_length=200)


class PolicyOut(BaseModel):
    schedule: str
    keep: int


class PolicyRequest(BaseModel):
    schedule: BackupSchedule
    keep: int = Field(default=7, ge=0, le=365)


def _out(b) -> BackupOut:
    return BackupOut(
        id=b.id,
        file_name=b.file_name,
        size_bytes=b.size_bytes,
        kind=str(b.kind),
        note=b.note,
        created_at=b.created_at.isoformat(),
    )


@router.get("/instances/{instance_id}/backups")
async def list_backups(
    instance_id: str,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    _: BackupsRead,
) -> dict:
    instance = await instances.get(instance_id)
    itens = await backups.list_for(instance)
    politica = await backups.get_policy(instance_id)
    return {
        "backups": [_out(b) for b in itens],
        "policy": PolicyOut(schedule=str(politica.schedule), keep=politica.keep),
        "spec": backups.describe(instance),
    }


@router.post("/instances/{instance_id}/backups", status_code=201)
async def create_backup(
    instance_id: str,
    body: CreateBackupRequest,
    request: Request,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    user: BackupsWrite,
) -> BackupOut:
    instance = await instances.get(instance_id)
    backup = await backups.create(instance, BackupKind.MANUAL, body.note)
    await _audit(request, f"backup.create instance={instance.name} file={backup.file_name}", user)
    return _out(backup)


@router.get("/instances/{instance_id}/backups/{backup_id}/download")
async def download_backup(
    instance_id: str,
    backup_id: str,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    _: BackupsRead,
) -> FileResponse:
    instance = await instances.get(instance_id)
    caminho = await backups.resolve_file(instance, backup_id)
    return FileResponse(caminho, filename=caminho.name, media_type="application/zip")


@router.post("/instances/{instance_id}/backups/{backup_id}/restore")
async def restore_backup(
    instance_id: str,
    backup_id: str,
    request: Request,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    user: BackupsWrite,
) -> dict:
    instance = await instances.get(instance_id)
    resultado = await backups.restore(instance, backup_id)
    await _audit(request, f"backup.restore instance={instance.name} backup={backup_id}", user)
    return resultado


@router.delete("/instances/{instance_id}/backups/{backup_id}", status_code=204)
async def delete_backup(
    instance_id: str,
    backup_id: str,
    request: Request,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    user: BackupsWrite,
) -> None:
    instance = await instances.get(instance_id)
    await backups.delete(instance, backup_id)
    await _audit(request, f"backup.delete instance={instance.name} backup={backup_id}", user)


@router.put("/instances/{instance_id}/backups/policy")
async def set_policy(
    instance_id: str,
    body: PolicyRequest,
    request: Request,
    instances: InstanceServiceDep,
    backups: BackupServiceDep,
    user: BackupsWrite,
) -> PolicyOut:
    instance = await instances.get(instance_id)
    await backups.set_policy(instance_id, BackupPolicy(schedule=body.schedule, keep=body.keep))
    await _audit(
        request,
        f"backup.policy instance={instance.name} schedule={body.schedule} keep={body.keep}",
        user,
    )
    return PolicyOut(schedule=str(body.schedule), keep=body.keep)


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
