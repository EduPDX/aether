"""Rotas do mapa-mundi: ligar/desligar/consultar o sidecar de mapa.

A URL final é montada pelo cliente (painel/launcher) a partir do endereço do
servidor que ele já conhece + a ``port`` devolvida aqui — o Core não presume o
próprio endereço público. Ver `application.worldmap` e o ADR 0001.
"""

from fastapi import APIRouter

from aether_core.interfaces.http.deps import (
    InstanceServiceDep,
    InstancesRead,
    MapServiceDep,
    PowerUse,
)

router = APIRouter(prefix="/instances/{instance_id}/map", tags=["map"])


@router.get("")
async def status(
    instance_id: str,
    instances: InstanceServiceDep,
    maps: MapServiceDep,
    _: InstancesRead,
) -> dict:
    instance = await instances.get(instance_id)
    return maps.status(instance)


@router.post("/enable")
async def enable(
    instance_id: str,
    instances: InstanceServiceDep,
    maps: MapServiceDep,
    _: PowerUse,
) -> dict:
    instance = await instances.get(instance_id)
    return await maps.enable(instance)


@router.post("/disable")
async def disable(
    instance_id: str,
    instances: InstanceServiceDep,
    maps: MapServiceDep,
    _: PowerUse,
) -> dict:
    instance = await instances.get(instance_id)
    return await maps.disable(instance)
