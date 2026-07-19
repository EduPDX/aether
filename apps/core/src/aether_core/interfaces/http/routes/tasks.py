"""Rotas de tarefas agendadas."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aether_core.domain.tasks import TaskKind, TaskSchedule
from aether_core.interfaces.http.deps import (
    InstanceServiceDep,
    PowerUse,
    TaskServiceDep,
)

router = APIRouter(prefix="/instances/{instance_id}/tasks", tags=["tasks"])


class TaskRequest(BaseModel):
    kind: TaskKind
    schedule: TaskSchedule
    at_hour: int = Field(default=4, ge=0, le=23)
    at_minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)
    enabled: bool = True
    command: str = ""
    warn_minutes: int = Field(default=0, ge=0, le=30)


def _out(t) -> dict:
    return {
        "id": t.id,
        "kind": str(t.kind),
        "schedule": str(t.schedule),
        "at_hour": t.at_hour,
        "at_minute": t.at_minute,
        "weekday": t.weekday,
        "enabled": t.enabled,
        "command": t.command,
        "warn_minutes": t.warn_minutes,
        "last_run": t.last_run.isoformat() if t.last_run else None,
        "description": t.describe(),
    }


@router.get("")
async def list_tasks(
    instance_id: str,
    instances: InstanceServiceDep,
    tasks: TaskServiceDep,
    _: PowerUse,
) -> list[dict]:
    await instances.get(instance_id)
    return [_out(t) for t in await tasks.list_for(instance_id)]


@router.post("", status_code=201)
async def create_task(
    instance_id: str,
    body: TaskRequest,
    request: Request,
    instances: InstanceServiceDep,
    tasks: TaskServiceDep,
    user: PowerUse,
) -> dict:
    instance = await instances.get(instance_id)
    tarefa = await tasks.create(instance_id, **body.model_dump())
    await _audit(request, f"task.create instance={instance.name} {tarefa.describe()}", user)
    return _out(tarefa)


@router.put("/{task_id}")
async def update_task(
    instance_id: str,
    task_id: str,
    body: TaskRequest,
    instances: InstanceServiceDep,
    tasks: TaskServiceDep,
    _: PowerUse,
) -> dict:
    await instances.get(instance_id)
    return _out(await tasks.update(instance_id, task_id, **body.model_dump()))


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    instance_id: str,
    task_id: str,
    instances: InstanceServiceDep,
    tasks: TaskServiceDep,
    _: PowerUse,
) -> None:
    await instances.get(instance_id)
    await tasks.delete(instance_id, task_id)


@router.post("/{task_id}/run")
async def run_task(
    instance_id: str,
    task_id: str,
    request: Request,
    instances: InstanceServiceDep,
    tasks: TaskServiceDep,
    user: PowerUse,
) -> dict:
    """Executa agora, sem esperar o horário — para testar o agendamento."""
    instance = await instances.get(instance_id)
    tarefa = await tasks._owned(instance_id, task_id)
    resultado = await tasks.run_now(instance, tarefa)
    await _audit(request, f"task.run instance={instance.name} {tarefa.describe()}", user)
    return resultado


async def _audit(request: Request, action: str, user) -> None:
    from aether_core.infrastructure.repositories import SqlAuditLog

    async with request.app.state.session_factory() as session:
        ip = request.client.host if request.client else None
        await SqlAuditLog(session).add(action, user, ip)
