"""Portas publicadas por uma instância em container."""

from pathlib import Path

from aether_sdk import LaunchContext, SupportsContainer
from fastapi import APIRouter, Request
from pydantic import BaseModel

from aether_core.application.ports_config import CHAVE, descrever, validar
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.instances import InstanceRuntime
from aether_core.interfaces.http.deps import InstanceServiceDep, InstancesRead, InstancesWrite

router = APIRouter(prefix="/instances/{instance_id}/ports", tags=["ports"])


class PortIn(BaseModel):
    container_port: int
    protocol: str = "tcp"
    host_port: int
    description: str = ""


class PortsRequest(BaseModel):
    ports: list[PortIn]


def _spec(request: Request, instance):
    """Spec do provider só para descobrir as portas padrão.

    Vem ``None`` quando o servidor ainda não foi instalado — a tela de portas
    precisa abrir mesmo assim, senão o usuário não consegue nem escolher a
    porta antes de instalar.
    """
    provider = request.app.state.providers.get(instance.provider_id)
    if not isinstance(provider, SupportsContainer):
        return None
    try:
        return provider.container_spec(
            LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)
        )
    except Exception:  # noqa: BLE001 - provider quebrado não trava a tela
        return None


@router.get("")
async def listar(
    request: Request, instance_id: str, svc: InstanceServiceDep, _: InstancesRead
) -> dict:
    instance = await svc.get(instance_id)
    return {
        "runtime": instance.runtime,
        "ports": descrever(_spec(request, instance), instance.provider_data),
        # Reiniciar é o que aplica: o Docker publica portas na criação do
        # container, não dá para mexer com ele de pé.
        "restart_required": request.app.state.supervisor.state(instance_id).value == "running",
    }


@router.put("")
async def salvar(
    request: Request,
    instance_id: str,
    body: PortsRequest,
    svc: InstanceServiceDep,
    _: InstancesWrite,
) -> dict:
    instance = await svc.get(instance_id)
    if instance.runtime != InstanceRuntime.DOCKER:
        raise ValidationFailedError("só instâncias em container publicam portas")

    # Conflito entre instâncias precisa ser pego aqui: o Docker só reclama na
    # hora de subir, e aí o servidor fica parado sem explicação.
    ocupadas: dict[tuple[int, str], str] = {}
    for outra in await svc.list_all():
        if outra.id == instance_id or outra.runtime != InstanceRuntime.DOCKER:
            continue
        for porta in descrever(_spec(request, outra), outra.provider_data):
            ocupadas[(porta["host_port"], porta["protocol"])] = outra.name

    portas = validar([p.model_dump() for p in body.ports], ocupadas=ocupadas)
    await svc.merge_provider_data(instance_id, {CHAVE: portas})
    instance = await svc.get(instance_id)
    return {
        "ports": descrever(_spec(request, instance), instance.provider_data),
        "restart_required": request.app.state.supervisor.state(instance_id).value == "running",
    }
