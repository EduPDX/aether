"""Server power and console routes."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from aether_core.interfaces.http.deps import InstanceServiceDep, PowerServiceDep

router = APIRouter(prefix="/instances/{instance_id}", tags=["power"])


class PowerRequest(BaseModel):
    action: Literal["start", "stop", "restart", "kill"]


class CommandRequest(BaseModel):
    command: str


@router.post("/power")
async def power(
    instance_id: str,
    body: PowerRequest,
    instances: InstanceServiceDep,
    power: PowerServiceDep,
) -> dict:
    instance = await instances.get(instance_id)
    action = {
        "start": power.start,
        "stop": power.stop,
        "restart": power.restart,
        "kill": power.kill,
    }[body.action]
    state = await action(instance)
    return {"state": state}


@router.get("/status")
async def status(instance_id: str, instances: InstanceServiceDep, power: PowerServiceDep) -> dict:
    instance = await instances.get(instance_id)
    return {"state": power.state(instance)}


@router.post("/command", status_code=204)
async def send_command(
    instance_id: str,
    body: CommandRequest,
    instances: InstanceServiceDep,
    power: PowerServiceDep,
) -> None:
    instance = await instances.get(instance_id)
    await power.send_command(instance, body.command)


@router.get("/logs")
async def logs(
    instance_id: str,
    instances: InstanceServiceDep,
    power: PowerServiceDep,
    tail: int = 200,
) -> dict:
    instance = await instances.get(instance_id)
    return {"lines": power.logs(instance, tail)}
