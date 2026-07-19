"""Tarefas agendadas: reiniciar, enviar comando, fazer backup.

Não é cron. Cron resolve expressões arbitrárias e erra em silêncio quando o
servidor fica fora do ar na hora exata; aqui a regra é "venceu e ainda não
rodou nesta janela", que se recupera sozinha de uma parada.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from aether_core.domain.errors import ValidationFailedError


class TaskKind(StrEnum):
    RESTART = "restart"
    COMMAND = "command"
    BACKUP = "backup"


class TaskSchedule(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# Sábado e domingo são masculinos: "todo domingo", não "toda domingo".
DIAS = (
    ("toda", "segunda"),
    ("toda", "terça"),
    ("toda", "quarta"),
    ("toda", "quinta"),
    ("toda", "sexta"),
    ("todo", "sábado"),
    ("todo", "domingo"),
)


@dataclass(frozen=True)
class ScheduledTask:
    id: str
    instance_id: str
    kind: TaskKind
    schedule: TaskSchedule
    """Hora do dia (0-23) para diário e semanal."""
    at_hour: int = 4
    """Minuto (0-59); em `hourly` é o único componente usado."""
    at_minute: int = 0
    """Dia da semana (0 = segunda) para o semanal."""
    weekday: int = 0
    enabled: bool = True
    """Comando a enviar, quando kind é COMMAND."""
    command: str = ""
    """Aviso no chat antes de reiniciar, em minutos. 0 = sem aviso."""
    warn_minutes: int = 0
    last_run: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(instance_id: str, kind: TaskKind, schedule: TaskSchedule, **kw) -> "ScheduledTask":
        return ScheduledTask(
            id=uuid.uuid4().hex,
            instance_id=instance_id,
            kind=kind,
            schedule=schedule,
            **kw,
        )

    def describe(self) -> str:
        hora = f"{self.at_hour:02d}:{self.at_minute:02d}"
        if self.schedule is TaskSchedule.HOURLY:
            quando = f"toda hora aos {self.at_minute:02d} min"
        elif self.schedule is TaskSchedule.DAILY:
            quando = f"todo dia às {hora}"
        else:
            artigo, dia = DIAS[self.weekday % 7]
            quando = f"{artigo} {dia} às {hora}"
        acao = {
            TaskKind.RESTART: "reiniciar o servidor",
            TaskKind.COMMAND: f"enviar “{self.command}”",
            TaskKind.BACKUP: "fazer backup",
        }[self.kind]
        return f"{acao}, {quando}"


def previous_occurrence(task: ScheduledTask, now: datetime) -> datetime:
    """O horário agendado mais recente que já passou.

    Comparar contra este instante — em vez de somar um intervalo à última
    execução — é o que faz a tarefa das 4h rodar às 4h, e não deslizar um
    pouco a cada dia por causa do atraso do ciclo anterior.
    """
    if task.schedule is TaskSchedule.HOURLY:
        alvo = now.replace(minute=task.at_minute, second=0, microsecond=0)
        return alvo if alvo <= now else alvo - timedelta(hours=1)

    alvo = now.replace(hour=task.at_hour, minute=task.at_minute, second=0, microsecond=0)
    if task.schedule is TaskSchedule.DAILY:
        return alvo if alvo <= now else alvo - timedelta(days=1)

    # Semanal: recua até o dia da semana escolhido (0 = segunda).
    recuo = (now.weekday() - task.weekday) % 7
    alvo = alvo - timedelta(days=recuo)
    return alvo if alvo <= now else alvo - timedelta(days=7)


PERIODO_MINUTOS = {
    TaskSchedule.HOURLY: 60,
    TaskSchedule.DAILY: 24 * 60,
    TaskSchedule.WEEKLY: 7 * 24 * 60,
}


def is_due(task: ScheduledTask, now: datetime, *, tolerance_minutes: int = 120) -> bool:
    """Se a tarefa deve rodar agora.

    A tolerância existe porque o ciclo do agendador não acorda no segundo
    exato e o servidor pode ter ficado fora do ar: uma tarefa das 4h ainda
    roda se o Core só voltar às 5h. Passada a janela, ela é pulada — reiniciar
    o servidor às 14h porque o agendamento das 4h foi perdido seria pior que
    não reiniciar.

    A janela nunca passa de metade do período: numa tarefa horária, tolerar
    duas horas faria disparar por um horário já vencido há mais de um ciclo.
    """
    if not task.enabled:
        return False
    janela = min(tolerance_minutes, PERIODO_MINUTOS[task.schedule] // 2)
    ocorrencia = previous_occurrence(task, now)
    if now - ocorrencia > timedelta(minutes=janela):
        return False
    return task.last_run is None or task.last_run < ocorrencia


_PERIGOSOS = re.compile(r"^\s*(stop|shutdown|ban|ban-ip|op|deop|whitelist\s+off)\b", re.I)


def validate_command(command: str) -> str:
    """Recusa o que transformaria um agendamento numa armadilha.

    `stop` agendado derruba o servidor sem que nada o suba de volta — quem
    quer reinício periódico deve usar a tarefa de reinício, que sobe de novo.
    """
    limpo = command.strip()
    if not limpo:
        raise ValidationFailedError("o comando não pode ser vazio")
    if len(limpo) > 300:
        raise ValidationFailedError("comando longo demais")
    if _PERIGOSOS.match(limpo):
        raise ValidationFailedError(
            f"“{limpo.split()[0]}” não pode ser agendado: use a tarefa de reinício "
            "para derrubar e subir o servidor"
        )
    return limpo
