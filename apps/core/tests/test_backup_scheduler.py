"""Agendador de backups: só dispara o que venceu e sobrevive a falhas.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from aether_core.application.backups import BackupService
from aether_core.application.scheduler import BackupScheduler
from aether_core.domain.backups import BackupKind, BackupPolicy, BackupSchedule


class _Instancia:
    def __init__(self, iid: str, nome: str) -> None:
        self.id = iid
        self.name = nome


class _RepoInstancias:
    def __init__(self, instancias) -> None:
        self._instancias = instancias

    async def list_all(self):
        return self._instancias


class _ServicoFalso:
    """Registra o que foi pedido, sem tocar em disco."""

    def __init__(self, vencidas: set[str], quebra: set[str] | None = None) -> None:
        self._vencidas = vencidas
        self._quebra = quebra or set()
        self.criados: list[tuple[str, BackupKind]] = []
        self.marcados: list[str] = []

    async def due(self, instance_id: str, now) -> bool:
        return instance_id in self._vencidas

    async def create(self, instance, kind=BackupKind.MANUAL, note=""):
        if instance.id in self._quebra:
            raise RuntimeError("disco cheio")
        self.criados.append((instance.id, kind))

        class _B:
            id = f"backup-{instance.id}"
            file_name = f"{instance.id}.zip"

        return _B()

    async def mark_run(self, instance_id: str, when) -> None:
        self.marcados.append(instance_id)


class _SessaoFalsa:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def _agendador(servico, instancias) -> BackupScheduler:
    return BackupScheduler(
        session_factory=lambda: _SessaoFalsa(),
        service_factory=lambda _s: servico,
        instances_factory=lambda _s: _RepoInstancias(instancias),
    )


def test_only_due_instances_are_backed_up():
    instancias = [_Instancia("a", "A"), _Instancia("b", "B"), _Instancia("c", "C")]
    servico = _ServicoFalso(vencidas={"a", "c"})

    criados = asyncio.run(_agendador(servico, instancias).tick())

    assert [i for i, _ in servico.criados] == ["a", "c"]
    assert all(kind is BackupKind.SCHEDULED for _, kind in servico.criados)
    assert servico.marcados == ["a", "c"]
    assert len(criados) == 2


def test_one_failing_instance_does_not_stop_the_others():
    """Sem isso, uma instância com disco cheio faria todas as outras pararem
    de fazer backup — e ninguém perceberia até precisar de um."""
    instancias = [_Instancia("a", "A"), _Instancia("b", "B"), _Instancia("c", "C")]
    servico = _ServicoFalso(vencidas={"a", "b", "c"}, quebra={"b"})

    criados = asyncio.run(_agendador(servico, instancias).tick())

    assert [i for i, _ in servico.criados] == ["a", "c"]
    assert "b" not in servico.marcados, "instância que falhou não deve marcar execução"
    assert len(criados) == 2


def test_nothing_due_means_nothing_created():
    servico = _ServicoFalso(vencidas=set())
    assert asyncio.run(_agendador(servico, [_Instancia("a", "A")]).tick()) == []
    assert servico.criados == []


def test_due_respects_the_configured_interval(tmp_path):
    """O intervalo do agendamento é obedecido pelo serviço real."""

    class _RepoMemoria:
        def __init__(self):
            self.politica = BackupPolicy()
            self.ultima = None

        async def get_policy(self, _):
            return self.politica

        async def last_run(self, _):
            return self.ultima

    repo = _RepoMemoria()
    servico = BackupService(repo, None, None, None, tmp_path)
    agora = datetime.now(UTC)

    async def venceu() -> bool:
        return await servico.due("i1", agora)

    # desligado nunca vence
    assert asyncio.run(venceu()) is False

    repo.politica = BackupPolicy(BackupSchedule.DAILY, keep=3)
    # nunca rodou: vence imediatamente
    assert asyncio.run(venceu()) is True

    repo.ultima = agora - timedelta(hours=5)
    assert asyncio.run(venceu()) is False, "5h não completam o ciclo diário"

    repo.ultima = agora - timedelta(hours=25)
    assert asyncio.run(venceu()) is True
