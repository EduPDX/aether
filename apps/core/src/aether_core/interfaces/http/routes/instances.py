"""Instance CRUD routes."""

from fastapi import APIRouter

from aether_core.interfaces.http.deps import InstanceServiceDep
from aether_core.interfaces.http.schemas import CreateInstanceRequest, InstanceOut

router = APIRouter(prefix="/instances", tags=["instances"])


@router.get("")
async def list_instances(svc: InstanceServiceDep) -> list[InstanceOut]:
    return [InstanceOut.from_domain(i) for i in await svc.list_all()]


@router.post("", status_code=201)
async def create_instance(body: CreateInstanceRequest, svc: InstanceServiceDep) -> InstanceOut:
    instance = await svc.create(body.name, body.provider_id, body.root_dir, body.content_dirs)
    return InstanceOut.from_domain(instance)


@router.get("/{instance_id}")
async def get_instance(instance_id: str, svc: InstanceServiceDep) -> InstanceOut:
    return InstanceOut.from_domain(await svc.get(instance_id))


@router.delete("/{instance_id}", status_code=204)
async def delete_instance(instance_id: str, svc: InstanceServiceDep) -> None:
    await svc.delete(instance_id)
