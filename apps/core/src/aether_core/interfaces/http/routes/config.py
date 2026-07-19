"""Schema-driven config routes (inclui o ícone do servidor)."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from aether_core.interfaces.http.deps import (
    ConfigRead,
    ConfigServiceDep,
    ConfigWrite,
    InstanceServiceDep,
    ServerIconServiceDep,
)

router = APIRouter(prefix="/instances/{instance_id}/config", tags=["config"])


class UpdateConfigRequest(BaseModel):
    schema_id: str
    values: dict[str, str]


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
