"""Laço de fundo que dispara os backups agendados.

Deliberadamente simples: acorda de tempos em tempos, pergunta a cada instância
se o agendamento venceu e roda o que venceu. Não tenta ser cron — sem
expressões, sem garantia de horário exato. Um backup que sai alguns minutos
atrasado ainda salva o mundo; complexidade de agendamento é o tipo de coisa
que quebra em silêncio e só se descobre quando o backup era necessário.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from aether_core.domain.backups import BackupKind

logger = logging.getLogger(__name__)

TICK_SECONDS = 60.0


class BackupScheduler:
    def __init__(self, session_factory, service_factory, instances_factory) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._instances_factory = instances_factory
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="backup-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(TICK_SECONDS)
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Um erro numa instância não pode derrubar o agendador inteiro,
                # senão todas as outras param de fazer backup em silêncio.
                logger.exception("falha no ciclo do agendador de backups")

    async def tick(self, now: datetime | None = None) -> list[str]:
        """Roda os backups vencidos. Devolve os ids gerados."""
        agora = now or datetime.now(UTC)
        criados: list[str] = []
        async with self._session_factory() as session:
            instances = self._instances_factory(session)
            service = self._service_factory(session)
            for instance in await instances.list_all():
                try:
                    if not await service.due(instance.id, agora):
                        continue
                    backup = await service.create(instance, BackupKind.SCHEDULED)
                    await service.mark_run(instance.id, agora)
                    criados.append(backup.id)
                    logger.info(
                        "backup agendado criado: instancia=%s arquivo=%s",
                        instance.name,
                        backup.file_name,
                    )
                except Exception:
                    logger.exception(
                        "falha ao criar backup agendado da instância %s", instance.name
                    )
        return criados
