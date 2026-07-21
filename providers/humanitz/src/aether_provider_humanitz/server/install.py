"""Instalação e atualização do servidor de HumanitZ via SteamCMD.

A mecânica é a comum a todo servidor Steam (``aether_sdk.steamcmd``); aqui fica
só o que é do HumanitZ.
"""

from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, VersionInfo, steamcmd

# O app do **servidor dedicado**, não o da loja (1622560). O SteamCMD baixa este.
STEAM_APP_ID = 2728330

# O servidor Linux do HumanitZ mora na branch ``linuxbranch``, não na ``public``:
# a ``public`` só distribui os arquivos de Windows (HumanitZServer.exe), e nem o
# ``+@sSteamCmdForcePlatformType linux`` traz um depot Linux que ela não tem.
# Este é o padrão quando o usuário não escolhe versão.
BRANCH_LINUX = "linuxbranch"

# Branches que não rodam no nosso container Linux — escondidas para o usuário não
# instalar, por engano, um servidor que nunca vai subir.
_BRANCHES_OCULTAS = {"public", "windowsbranch"}

TAMANHO_DO_JOGO = 2 * 1024**3
"""~1,5 GB medidos no app 2728330 em 2026-07 (SizeOnDisk 1.472.520.666)."""

DISCO_NECESSARIO = 2 * TAMANHO_DO_JOGO + 1024**3
"""O SteamCMD baixa numa pasta de trabalho antes de gravar os arquivos finais,
então em algum momento as duas cópias coexistem; a folga de 1 GB cobre saves."""


def install_spec(ctx: LaunchContext, version: str) -> ContainerSpec:
    return steamcmd.install_spec(STEAM_APP_ID, version or BRANCH_LINUX)


def install_disk_bytes(version: str) -> int:
    return DISCO_NECESSARIO


def versions_spec() -> ContainerSpec:
    return steamcmd.versions_spec(STEAM_APP_ID)


def parse_versions(stdout: str) -> list[VersionInfo]:
    """Só as branches que rodam em Linux; a ``linuxbranch`` vira a recomendada.

    A ``public`` e a ``windowsbranch`` distribuem binários de Windows e não
    sobem no nosso container, então some da lista — oferecê-las seria convidar
    o usuário a instalar um servidor que não inicia.
    """
    saida: list[VersionInfo] = []
    for v in steamcmd.parse_branches(stdout):
        if v.id in _BRANCHES_OCULTAS:
            continue
        if v.id == BRANCH_LINUX:
            v = v.model_copy(update={"label": "Mais recente (Linux)", "stable": True})
        saida.append(v)
    return saida


def installed_version(root_dir: Path) -> str:
    return steamcmd.installed_build(Path(root_dir), STEAM_APP_ID)
