"""Schema-driven config routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from aether_core.interfaces.http.deps import (
    ConfigRead,
    ConfigServiceDep,
    ConfigWrite,
    InstanceServiceDep,
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
