"""O que compõe um backup de um servidor Satisfactory."""

from pathlib import Path

from aether_sdk import BackupSpec, QuiescePlan


def backup_spec(root: Path) -> BackupSpec:
    # Os saves e a config do servidor moram sob FactoryGame/Saved/. Os arquivos
    # do jogo (server/Engine, server/FactoryGame/Content) ficam de fora: são
    # ~3 GB re-baixáveis pelo SteamCMD.
    return BackupSpec(
        include=(
            "server/FactoryGame/Saved/SaveGames/**",
            "server/FactoryGame/Saved/Config/**",
        ),
        exclude=("**/*.log", "**/Logs/**"),
        summary=(
            "Saves (SaveGames/) e a configuração do servidor (Saved/Config/). "
            "Não inclui os arquivos do jogo: o SteamCMD baixa tudo de novo."
        ),
    )


def quiesce_plan() -> QuiescePlan:
    """Satisfactory faz autosave; o intervalo de settle cobre a gravação
    pendente. Não há comando de save via stdin no servidor dedicado."""
    return QuiescePlan(before=(), after=(), settle_seconds=5.0)
