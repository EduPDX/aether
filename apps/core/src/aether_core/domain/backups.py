"""Backup de instância: entidade, agendamento e política de retenção."""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class BackupKind(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class BackupSchedule(StrEnum):
    OFF = "off"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


INTERVALO_SEGUNDOS: dict[BackupSchedule, int] = {
    BackupSchedule.HOURLY: 3600,
    BackupSchedule.DAILY: 86_400,
    BackupSchedule.WEEKLY: 604_800,
}


@dataclass(frozen=True)
class Backup:
    id: str
    instance_id: str
    file_name: str
    size_bytes: int
    kind: BackupKind
    note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(
        instance_id: str,
        file_name: str,
        size_bytes: int,
        kind: BackupKind,
        note: str = "",
    ) -> "Backup":
        return Backup(
            id=uuid.uuid4().hex,
            instance_id=instance_id,
            file_name=file_name,
            size_bytes=size_bytes,
            kind=kind,
            note=note,
        )


@dataclass(frozen=True)
class BackupPolicy:
    schedule: BackupSchedule = BackupSchedule.OFF
    """Quantos backups manter. 0 = manter todos (o disco que se cuide)."""
    keep: int = 7

    def interval_seconds(self) -> int | None:
        return INTERVALO_SEGUNDOS.get(self.schedule)


_SEGURO = re.compile(r"[^A-Za-z0-9_.-]+")


def backup_file_name(
    instance_name: str, when: datetime, kind: BackupKind, token: str
) -> str:
    """Nome ordenável, único e seguro para uso como caminho.

    O carimbo vem primeiro para a ordenação alfabética coincidir com a
    cronológica, e o nome da instância é higienizado: ele vem do usuário e
    acaba virando caminho em disco.

    O `token` é obrigatório porque o carimbo tem resolução de segundos: dois
    backups no mesmo segundo — o agendado junto de um manual, ou o de
    segurança que o restore cria — gerariam o mesmo nome e um sobrescreveria
    o outro. Um backup que apaga outro backup é a falha mais cara possível
    aqui, e foi assim que o restore chegou a restaurar o estado errado.
    """
    carimbo = when.astimezone(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    limpo = _SEGURO.sub("-", instance_name).strip("-") or "instancia"
    sufixo = _SEGURO.sub("", token)[:8] or uuid.uuid4().hex[:8]
    return f"{carimbo}_{limpo}_{kind.value}_{sufixo}.zip"


def select_for_pruning(backups: list[Backup], policy: BackupPolicy) -> list[Backup]:
    """Quais backups apagar para respeitar a retenção.

    Backups manuais nunca são podados: o usuário os criou de propósito, muitas
    vezes antes de mexer em algo arriscado. A retenção governa só os
    automáticos, que se repetem sozinhos.
    """
    if policy.keep <= 0:
        return []
    automaticos = [b for b in backups if b.kind is BackupKind.SCHEDULED]
    automaticos.sort(key=lambda b: b.created_at, reverse=True)
    return automaticos[policy.keep :]
