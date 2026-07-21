"""O que compõe um backup de um servidor HumanitZ."""

from pathlib import Path

from aether_sdk import BackupSpec, QuiescePlan


def backup_spec(root: Path) -> BackupSpec:
    # Saves e config ficam sob HumanitZServer/. Os arquivos do jogo (~1,5 GB)
    # ficam de fora: o SteamCMD os baixa de novo.
    return BackupSpec(
        include=(
            "server/HumanitZServer/Saved/SaveGames/**",
            "server/HumanitZServer/GameServerSettings.ini",
        ),
        exclude=("**/*.log", "**/Logs/**"),
        summary=(
            "Saves (SaveGames/) e o GameServerSettings.ini. Não inclui os "
            "arquivos do jogo: o SteamCMD baixa tudo de novo."
        ),
    )


def quiesce_plan() -> QuiescePlan:
    """O servidor faz autosave por intervalo; o settle cobre a gravação
    pendente. Não há comando de save via stdin."""
    return QuiescePlan(before=(), after=(), settle_seconds=5.0)
