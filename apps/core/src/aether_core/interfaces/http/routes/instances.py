"""Instance CRUD routes."""

from contextlib import suppress

from fastapi import APIRouter, Request

from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import InstanceState
from aether_core.interfaces.http.deps import InstanceServiceDep, InstancesRead, InstancesWrite
from aether_core.interfaces.http.schemas import CreateInstanceRequest, InstanceOut

router = APIRouter(prefix="/instances", tags=["instances"])


def _out(request: Request, instance) -> InstanceOut:
    return InstanceOut.from_domain(instance, state=request.app.state.supervisor.state(instance.id))


@router.get("")
async def list_instances(
    request: Request, svc: InstanceServiceDep, _: InstancesRead
) -> list[InstanceOut]:
    return [_out(request, i) for i in await svc.list_all()]


@router.post("", status_code=201)
async def create_instance(
    request: Request, body: CreateInstanceRequest, svc: InstanceServiceDep, _: InstancesWrite
) -> InstanceOut:
    instance = await svc.create(
        body.name,
        body.provider_id,
        body.root_dir,
        runtime=body.runtime,
        content_dirs=body.content_dirs,
        provider_data=body.provider_data,
        provision_values=body.provision_values,
    )

    # Instância criada do zero já entra instalando: é o que o usuário pediu ao
    # escolher a versão, e o download é longo demais para esperar um clique.
    installs = request.app.state.installs
    if body.provision_values is not None and body.version is not None:
        with suppress(ValidationFailedError, ConflictError):
            await installs.start(instance, body.version or "public")

    return _out(request, instance)


@router.get("/{instance_id}")
async def get_instance(
    request: Request, instance_id: str, svc: InstanceServiceDep, _: InstancesRead
) -> InstanceOut:
    return _out(request, await svc.get(instance_id))


@router.delete("/{instance_id}", status_code=204)
async def delete_instance(
    request: Request, instance_id: str, svc: InstanceServiceDep, _: InstancesWrite
) -> None:
    state = request.app.state.supervisor.state(instance_id)
    if state not in (InstanceState.STOPPED, InstanceState.CRASHED):
        raise ConflictError(f"stop the instance before removing it (state: {state})")
    await svc.delete(instance_id)
