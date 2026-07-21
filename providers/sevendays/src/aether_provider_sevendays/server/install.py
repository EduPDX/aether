"""Instalação e atualização do servidor de 7 Days to Die.

A mecânica do SteamCMD é comum a todo servidor Steam e mora em
``aether_sdk.steamcmd``; aqui fica só o que é do 7DTD: o app id e o quanto a
instalação ocupa em disco.
"""

from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, VersionInfo, steamcmd

STEAM_APP_ID = 294420

TAMANHO_DO_JOGO = 18 * 1024**3
"""~17,5 GB medidos no app 294420 em 2026-07 (a Steam informa 17.546.210.919 B)."""

DISCO_NECESSARIO = 2 * TAMANHO_DO_JOGO
"""O SteamCMD baixa tudo em ``steamapps/downloading`` e só depois grava os
arquivos finais, então em algum momento as duas cópias coexistem. Pedir menos
que o dobro é convidar a falha do fim: num LXC com 35 GB livres a instalação
morreu em 99,6% com ``state is 0x602`` e deixou um servidor que não inicia."""


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
