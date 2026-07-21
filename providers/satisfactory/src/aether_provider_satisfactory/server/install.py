"""Instalação e atualização do servidor de Satisfactory via SteamCMD.

A mecânica é a comum a todo servidor Steam (``aether_sdk.steamcmd``); aqui fica
só o que é do Satisfactory.
"""

from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, VersionInfo, steamcmd

# O app do **servidor dedicado**, não o da loja (526870). O SteamCMD baixa este.
STEAM_APP_ID = 1690800

TAMANHO_DO_JOGO = 3 * 1024**3
"""~2,8 GB medidos no app 1690800 em 2026-07 (SizeOnDisk 2.902.851.625)."""

DISCO_NECESSARIO = 2 * TAMANHO_DO_JOGO + 1024**3
"""O SteamCMD baixa numa pasta de trabalho antes de gravar os arquivos finais,
então em algum momento as duas cópias coexistem; a folga de 1 GB cobre saves."""


def install_spec(ctx: LaunchContext, version: str) -> ContainerSpec:
    return steamcmd.install_spec(STEAM_APP_ID, version)


def install_disk_bytes(version: str) -> int:
    return DISCO_NECESSARIO


def versions_spec() -> ContainerSpec:
    return steamcmd.versions_spec(STEAM_APP_ID)


def parse_versions(stdout: str) -> list[VersionInfo]:
    return steamcmd.parse_branches(stdout)


def installed_version(root_dir: Path) -> str:
    return steamcmd.installed_build(Path(root_dir), STEAM_APP_ID)
