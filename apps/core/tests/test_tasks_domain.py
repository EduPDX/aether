"""Regra de disparo das tarefas agendadas — lógica pura, sem I/O.

É aqui que mora o risco do agendamento: rodar duas vezes, deslizar de horário,
ou reiniciar o servidor no meio da tarde porque a janela da madrugada passou.
"""

from datetime import datetime, timedelta

import pytest
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.tasks import (
    ScheduledTask,
    TaskKind,
    TaskSchedule,
    is_due,
    previous_occurrence,
    validate_command,
)


def _tarefa(**kw) -> ScheduledTask:
    base = dict(
        instance_id="i1",
        kind=TaskKind.RESTART,
        schedule=TaskSchedule.DAILY,
        at_hour=4,
        at_minute=0,
    )
    base.update(kw)
    return ScheduledTask.new(**base)


def test_daily_runs_at_the_configured_hour():
    tarefa = _tarefa()
    # 03:59 — ainda não é hora
    assert is_due(tarefa, datetime(2026, 7, 19, 3, 59)) is False
    # 04:00 em ponto
    assert is_due(tarefa, datetime(2026, 7, 19, 4, 0)) is True
    # 04:30, o ciclo acordou atrasado — ainda vale
    assert is_due(tarefa, datetime(2026, 7, 19, 4, 30)) is True


def test_task_does_not_run_twice_in_the_same_window():
    """O ciclo roda de minuto em minuto: sem isso reiniciaria em looping."""
    agora = datetime(2026, 7, 19, 4, 0)
    tarefa = _tarefa()
    assert is_due(tarefa, agora) is True

    executada = ScheduledTask(**{**tarefa.__dict__, "last_run": agora})
    assert is_due(executada, agora + timedelta(minutes=1)) is False
    assert is_due(executada, agora + timedelta(minutes=59)) is False


def test_task_runs_again_the_next_day():
    ontem = datetime(2026, 7, 18, 4, 0)
    tarefa = ScheduledTask(**{**_tarefa().__dict__, "last_run": ontem})

    assert is_due(tarefa, datetime(2026, 7, 19, 3, 59)) is False
    assert is_due(tarefa, datetime(2026, 7, 19, 4, 0)) is True


def test_a_long_outage_does_not_trigger_a_restart_in_the_afternoon():
    """Servidor fora do ar das 4h às 14h: reiniciar às 14h seria pior que pular."""
    tarefa = _tarefa()
    assert is_due(tarefa, datetime(2026, 7, 19, 5, 30)) is True, "1h30 de atraso ainda vale"
    assert is_due(tarefa, datetime(2026, 7, 19, 14, 0)) is False, "10h depois, não"


def test_hourly_uses_only_the_minute():
    tarefa = _tarefa(schedule=TaskSchedule.HOURLY, at_minute=30)
    assert is_due(tarefa, datetime(2026, 7, 19, 10, 29)) is False
    assert is_due(tarefa, datetime(2026, 7, 19, 10, 30)) is True
    assert is_due(tarefa, datetime(2026, 7, 19, 11, 30)) is True


def test_weekly_runs_on_the_chosen_weekday():
    # 20/07/2026 é uma segunda-feira
    tarefa = _tarefa(schedule=TaskSchedule.WEEKLY, weekday=0, at_hour=5)
    assert datetime(2026, 7, 20).weekday() == 0

    assert is_due(tarefa, datetime(2026, 7, 20, 5, 0)) is True
    assert is_due(tarefa, datetime(2026, 7, 21, 5, 0)) is False, "terça não dispara"

    executada = ScheduledTask(**{**tarefa.__dict__, "last_run": datetime(2026, 7, 20, 5, 0)})
    assert is_due(executada, datetime(2026, 7, 27, 5, 0)) is True, "na segunda seguinte, sim"


def test_previous_occurrence_does_not_drift():
    """A âncora é o horário agendado, não 'última execução + 24h'.

    Com intervalo, um ciclo atrasado empurraria o horário para frente todo dia
    até a tarefa da madrugada acabar rodando de tarde.
    """
    tarefa = _tarefa()
    assert previous_occurrence(tarefa, datetime(2026, 7, 19, 4, 47)) == datetime(2026, 7, 19, 4, 0)
    assert previous_occurrence(tarefa, datetime(2026, 7, 19, 3, 0)) == datetime(2026, 7, 18, 4, 0)


def test_disabled_task_never_runs():
    tarefa = _tarefa(enabled=False)
    assert is_due(tarefa, datetime(2026, 7, 19, 4, 0)) is False


def test_dangerous_commands_are_refused():
    """`stop` agendado derruba o servidor sem nada para subi-lo de volta."""
    for perigoso in ["stop", "  STOP  ", "shutdown", "op alguem", "ban jogador"]:
        with pytest.raises(ValidationFailedError):
            validate_command(perigoso)


def test_ordinary_commands_pass():
    assert validate_command("  say bom dia  ") == "say bom dia"
    assert validate_command("save-all") == "save-all"
    # "stopwatch" não é "stop": a checagem é por palavra, não por prefixo
    assert validate_command("stopwatch start") == "stopwatch start"


def test_empty_and_oversized_commands_are_refused():
    with pytest.raises(ValidationFailedError):
        validate_command("   ")
    with pytest.raises(ValidationFailedError):
        validate_command("say " + "a" * 400)


def test_description_is_readable():
    assert "todo dia às 04:00" in _tarefa().describe()
    assert "reiniciar o servidor" in _tarefa().describe()
    cmd = _tarefa(kind=TaskKind.COMMAND, command="say oi", schedule=TaskSchedule.HOURLY)
    assert "say oi" in cmd.describe()
    # concordância: sábado e domingo são masculinos
    assert "todo domingo" in _tarefa(schedule=TaskSchedule.WEEKLY, weekday=6).describe()
    assert "todo sábado" in _tarefa(schedule=TaskSchedule.WEEKLY, weekday=5).describe()
    assert "toda segunda" in _tarefa(schedule=TaskSchedule.WEEKLY, weekday=0).describe()
