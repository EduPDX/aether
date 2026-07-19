"""Execução das tarefas agendadas."""

import asyncio
import logging
from datetime import datetime
from typing import Protocol

from aether_core.application.events import EventBus
from aether_core.domain.errors import NotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState
from aether_core.domain.tasks import ScheduledTask, TaskKind, validate_command

logger = logging.getLogger(__name__)


class TaskRepository(Protocol):
    async def add(self, task: ScheduledTask) -> None: ...

    async def list_for(self, instance_id: str) -> list[ScheduledTask]: ...

    async def list_all(self) -> list[ScheduledTask]: ...

    async def get(self, task_id: str) -> ScheduledTask | None: ...

    async def save(self, task: ScheduledTask) -> None: ...

    async def delete(self, task_id: str) -> bool: ...


class PowerLike(Protocol):
    async def restart(self, instance: Instance) -> None: ...


class SupervisorLike(Protocol):
    def state(self, instance_id: str) -> InstanceState: ...

    async def send_command(self, instance_id: str, command: str) -> None: ...


class TaskService:
    def __init__(
        self,
        repo: TaskRepository,
        supervisor: SupervisorLike,
        power: PowerLike,
        bus: EventBus,
    ) -> None:
        self._repo = repo
        self._supervisor = supervisor
        self._power = power
        self._bus = bus

    async def list_for(self, instance_id: str) -> list[ScheduledTask]:
        return await self._repo.list_for(instance_id)

    async def create(self, instance_id: str, **campos) -> ScheduledTask:
        if campos.get("kind") is TaskKind.COMMAND:
            campos["command"] = validate_command(campos.get("command", ""))
        tarefa = ScheduledTask.new(instance_id=instance_id, **campos)
        await self._repo.add(tarefa)
        return tarefa

    async def update(self, instance_id: str, task_id: str, **campos) -> ScheduledTask:
        tarefa = await self._owned(instance_id, task_id)
        if "command" in campos and (campos.get("kind") or tarefa.kind) is TaskKind.COMMAND:
            campos["command"] = validate_command(campos["command"])
        atualizada = ScheduledTask(**{**tarefa.__dict__, **campos})
        await self._repo.save(atualizada)
        return atualizada

    async def delete(self, instance_id: str, task_id: str) -> None:
        await self._owned(instance_id, task_id)
        await self._repo.delete(task_id)

    async def _owned(self, instance_id: str, task_id: str) -> ScheduledTask:
        tarefa = await self._repo.get(task_id)
        # Confere o dono: um id válido de outra instância não pode ser mexido.
        if tarefa is None or tarefa.instance_id != instance_id:
            raise NotFoundError(f"tarefa não encontrada: {task_id}")
        return tarefa

    async def run_now(self, instance: Instance, task: ScheduledTask) -> dict:
        """Executa a tarefa. Usado pelo agendador e pelo botão "executar agora"."""
        if task.kind is TaskKind.COMMAND:
            if self._supervisor.state(instance.id) is not InstanceState.RUNNING:
                raise ValidationFailedError(
                    "o servidor precisa estar no ar para receber comandos"
                )
            await self._supervisor.send_command(instance.id, task.command)
            resultado = {"sent": task.command}

        elif task.kind is TaskKind.RESTART:
            rodando = self._supervisor.state(instance.id) is InstanceState.RUNNING
            if rodando and task.warn_minutes > 0:
                # Avisa quem está jogando antes de derrubar. Sem isso o
                # reinício da madrugada pega alguém no meio de uma construção.
                await self._avisar(instance, task.warn_minutes)
            await self._power.restart(instance)
            resultado = {"restarted": True, "warned": rodando and task.warn_minutes > 0}

        else:
            raise ValidationFailedError(f"tipo de tarefa sem execução: {task.kind}")

        await self._bus.publish(
            "task.executed",
            {"instance_id": instance.id, "task_id": task.id, "kind": str(task.kind)},
        )
        return resultado

    async def _avisar(self, instance: Instance, minutos: int) -> None:
        """Conta regressiva no chat antes do reinício."""
        marcos = [m for m in (minutos, 5, 1) if m <= minutos]
        anterior = None
        for marco in sorted(set(marcos), reverse=True):
            if anterior is not None:
                await asyncio.sleep((anterior - marco) * 60)
            try:
                await self._supervisor.send_command(
                    instance.id, f"say O servidor reinicia em {marco} minuto(s)."
                )
            except Exception:
                logger.warning("não consegui avisar o chat de %s", instance.name)
                return
            anterior = marco
        if anterior:
            await asyncio.sleep(anterior * 60)

    async def mark_run(self, task: ScheduledTask, when: datetime) -> None:
        await self._repo.save(ScheduledTask(**{**task.__dict__, "last_run": when}))

    async def due_tasks(self, now: datetime) -> list[ScheduledTask]:
        from aether_core.domain.tasks import is_due

        return [t for t in await self._repo.list_all() if is_due(t, now)]
