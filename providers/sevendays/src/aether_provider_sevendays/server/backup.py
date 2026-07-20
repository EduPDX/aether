"""O que compõe um backup de um servidor 7 Days to Die."""

from pathlib import Path

from aether_sdk import BackupSpec, QuiescePlan


def backup_spec(root: Path) -> BackupSpec:
    # UserData concentra saves e mundos gerados (UserDataFolder aponta para
    # lá de propósito); o serverconfig é pequeno e insubstituível. A pasta
    # server/ fica de fora: são 15+ GB re-baixáveis pelo SteamCMD.
    return BackupSpec(
        include=("UserData/**", "serverconfig.xml", "server/Mods/**"),
        exclude=("**/*.log", "UserData/Logs/**"),
        summary=(
            "Saves e mundos gerados (UserData/), o serverconfig.xml e os mods. "
            "Não inclui os arquivos do jogo: o SteamCMD baixa tudo de novo."
        ),
    )


def quiesce_plan() -> QuiescePlan:
    """``saveworld`` força a gravação pendente antes da cópia. O jogo não tem
    um save-off como o Minecraft; o intervalo de settle cobre a escrita."""
    return QuiescePlan(before=("saveworld",), after=(), settle_seconds=5.0)
