"""Schema-driven config routes (inclui o ícone do servidor)."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from aether_core.application.config_raw import VALIDADORES
from aether_core.interfaces.http.deps import (
    ConfigRead,
    ConfigServiceDep,
    ConfigWrite,
    InstanceServiceDep,
    RawConfigServiceDep,
    ServerIconServiceDep,
)

router = APIRouter(prefix="/instances/{instance_id}/config", tags=["config"])


class UpdateConfigRequest(BaseModel):
    schema_id: str
    values: dict[str, str]


class RawConfigRequest(BaseModel):
    schema_id: str
    content: str


class ValidateConfigRequest(BaseModel):
    schema_id: str
    content: str


@router.get("")
async def list_configs(
    instance_id: str,
    instances: InstanceServiceDep,
    config: ConfigServiceDep,
    _: ConfigRead,
) -> list[dict]:
    instance = await instances.get(instance_id)
    return await config.list_configs(instance)


@router.put("", status_code=204)
async def update_config(
    instance_id: str,
    body: UpdateConfigRequest,
    instances: InstanceServiceDep,
    config: ConfigServiceDep,
    _: ConfigWrite,
) -> None:
    instance = await instances.get(instance_id)
    await config.update_config(instance, body.schema_id, body.values)


# ------------------------------------------------------- modo avançado (cru) --


@router.get("/raw")
async def read_raw(
    instance_id: str,
    schema_id: str,
    instances: InstanceServiceDep,
    raw: RawConfigServiceDep,
    _: ConfigRead,
) -> dict:
    instance = await instances.get(instance_id)
    return await raw.read(instance, schema_id)


@router.post("/raw/validate")
async def validate_raw(
    instance_id: str,
    body: ValidateConfigRequest,
    instances: InstanceServiceDep,
    raw: RawConfigServiceDep,
    _: ConfigRead,
) -> dict:
    """Valida sem gravar — o editor avisa antes de o usuário salvar."""
    instance = await instances.get(instance_id)
    schema = raw.schema_de(instance, body.schema_id)
    validador = VALIDADORES.get(schema.format)
    erro = validador(body.content) if validador else None
    if erro is None:
        return {"valid": True}
    return {
        "valid": False,
        "message": erro.message,
        "line": erro.line,
        "column": erro.column,
    }


@router.put("/raw")
async def write_raw(
    instance_id: str,
    body: RawConfigRequest,
    instances: InstanceServiceDep,
    raw: RawConfigServiceDep,
    _: ConfigWrite,
) -> dict:
    instance = await instances.get(instance_id)
    return await raw.write(instance, body.schema_id, body.content)


@router.post("/raw/restore")
async def restore_raw(
    instance_id: str,
    schema_id: str,
    instances: InstanceServiceDep,
    raw: RawConfigServiceDep,
    _: ConfigWrite,
) -> dict:
    instance = await instances.get(instance_id)
    return await raw.restore(instance, schema_id)


# ------------------------------------------------------------------ ícone --


@router.get("/icon", tags=["config"])
async def get_icon(
    instance_id: str,
    instances: InstanceServiceDep,
    icons: ServerIconServiceDep,
    _: ConfigRead,
) -> FileResponse:
    instance = await instances.get(instance_id)
    return FileResponse(icons.resolve(instance), media_type="image/png")


@router.put("/icon", tags=["config"])
async def put_icon(
    instance_id: str,
    instances: InstanceServiceDep,
    icons: ServerIconServiceDep,
    _: ConfigWrite,
    upload: Annotated[UploadFile, File()],
) -> dict:
    """Recebe o PNG 64x64 já redimensionado pelo navegador."""
    instance = await instances.get(instance_id)
    return await icons.save(instance, await upload.read())


@router.delete("/icon", status_code=204, tags=["config"])
async def delete_icon(
    instance_id: str,
    instances: InstanceServiceDep,
    icons: ServerIconServiceDep,
    _: ConfigWrite,
) -> None:
    instance = await instances.get(instance_id)
    await icons.delete(instance)
