"""Regras de nomeação e retenção de backup (lógica pura, sem I/O)."""

from datetime import UTC, datetime, timedelta

from aether_core.domain.backups import (
    Backup,
    BackupKind,
    BackupPolicy,
    BackupSchedule,
    backup_file_name,
    select_for_pruning,
)


def _backup(kind: BackupKind, dias_atras: int) -> Backup:
    b = Backup.new("i1", f"{kind.value}-{dias_atras}.zip", 10, kind)
    return Backup(**{**b.__dict__, "created_at": datetime.now(UTC) - timedelta(days=dias_atras)})


def test_file_name_is_sortable_and_path_safe():
    quando = datetime(2026, 7, 18, 13, 5, 9, tzinfo=UTC)
    nome = backup_file_name("Servidor do Edu / teste", quando, BackupKind.MANUAL, "abc123")

    assert nome.startswith("2026-07-18_13-05-09_")
    assert nome.endswith(".zip")
    assert "_manual_" in nome
    # o nome vem do usuário e vira caminho: nada de barra nem espaço
    assert "/" not in nome and "\\" not in nome and " " not in nome

    anterior = backup_file_name("Servidor", quando - timedelta(hours=1), BackupKind.MANUAL, "abc")
    assert anterior < nome, "ordem alfabética deve coincidir com a cronológica"


def test_two_backups_in_the_same_second_do_not_collide():
    """Regressão: o carimbo tem resolução de segundos.

    Sem um discriminador, o backup de segurança criado pelo restore nascia com
    o mesmo nome do backup que estava sendo restaurado e o sobrescrevia — o
    restore então devolvia o estado errado.
    """
    quando = datetime(2026, 7, 18, 13, 5, 9, tzinfo=UTC)
    a = backup_file_name("Servidor", quando, BackupKind.MANUAL, "aaaaaaaa")
    b = backup_file_name("Servidor", quando, BackupKind.MANUAL, "bbbbbbbb")
    assert a != b


def test_instance_name_without_safe_characters_still_yields_a_name():
    nome = backup_file_name("///", datetime(2026, 1, 1, tzinfo=UTC), BackupKind.SCHEDULED, "t")
    assert "instancia" in nome


def test_token_without_safe_characters_still_yields_a_unique_suffix():
    nome = backup_file_name("Srv", datetime(2026, 1, 1, tzinfo=UTC), BackupKind.MANUAL, "///")
    assert nome.endswith(".zip")
    assert nome.count("_") >= 3, "deve haver sufixo mesmo com token inválido"


def test_pruning_keeps_the_newest_scheduled_backups():
    backups = [_backup(BackupKind.SCHEDULED, d) for d in range(5)]
    apagar = select_for_pruning(backups, BackupPolicy(BackupSchedule.DAILY, keep=3))

    assert len(apagar) == 2
    # os removidos são os mais antigos
    assert {b.file_name for b in apagar} == {"scheduled-3.zip", "scheduled-4.zip"}


def test_manual_backups_are_never_pruned():
    """Backup manual costuma ser o 'antes de mexer' — a rotina não pode comê-lo."""
    backups = [_backup(BackupKind.MANUAL, d) for d in range(5)]
    assert select_for_pruning(backups, BackupPolicy(BackupSchedule.DAILY, keep=1)) == []

    misto = [*backups, *[_backup(BackupKind.SCHEDULED, d) for d in range(4)]]
    apagar = select_for_pruning(misto, BackupPolicy(BackupSchedule.DAILY, keep=2))
    assert all(b.kind is BackupKind.SCHEDULED for b in apagar)
    assert len(apagar) == 2


def test_keep_zero_means_keep_everything():
    backups = [_backup(BackupKind.SCHEDULED, d) for d in range(9)]
    assert select_for_pruning(backups, BackupPolicy(BackupSchedule.HOURLY, keep=0)) == []


def test_schedule_intervals():
    assert BackupPolicy(BackupSchedule.OFF).interval_seconds() is None
    assert BackupPolicy(BackupSchedule.HOURLY).interval_seconds() == 3600
    assert BackupPolicy(BackupSchedule.DAILY).interval_seconds() == 86_400
