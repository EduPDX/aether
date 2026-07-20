"""Instalação e atualização do servidor via SteamCMD.

Duas armadilhas do SteamCMD moram aqui, ambas custaram depuração:

- o app 294420 é do tipo *Tool*, e para esses o SteamCMD não resolve a
  plataforma sozinho: sem ``+@sSteamCmdForcePlatformType linux`` **antes** do
  login ele aborta com "Missing configuration" sem baixar nada;
- ele recusa rodar como root ("Missing file permissions"), daí o ``run_as``.

As versões vêm das *branches* que a própria Steam publica para o app, então a
lista acompanha o jogo sem ninguém editar o painel a cada lançamento.
"""

import re
from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, VersionInfo, VolumeMount

from aether_provider_sevendays.server.container import IMAGE, INSTALL_DIR, RUN_AS

STEAM_APP_ID = 294420
BRANCH_PADRAO = "public"
HOME_STEAM = "/home/steam"

TAMANHO_DO_JOGO = 18 * 1024**3
"""~17,5 GB medidos no app 294420 em 2026-07 (a Steam informa 17.546.210.919 B)."""

DISCO_NECESSARIO = 2 * TAMANHO_DO_JOGO
"""O SteamCMD baixa tudo em ``steamapps/downloading`` e só depois grava os
arquivos finais, então em algum momento as duas cópias coexistem. Pedir menos
que o dobro é convidar a falha do fim: num LXC com 35 GB livres a instalação
morreu em 99,6% com ``state is 0x602`` e deixou um servidor que não inicia."""

_STEAMCMD = "/home/steam/steamcmd/steamcmd.sh +@sSteamCmdForcePlatformType linux"

# O dump do `app_info_print` é um VDF aninhado. Só o bloco "branches" interessa,
# e dentro dele cada chave no nível certo de indentação é uma branch.
_BLOCO_BRANCHES = re.compile(r'"branches"\s*\{(.*)', re.DOTALL)
_BRANCH = re.compile(r'^\t{3}"([^"]+)"\s*$', re.MULTILINE)
_CAMPO = re.compile(r'^\t{4}"(buildid|description)"\s+"([^"]*)"', re.MULTILINE)


def install_spec(ctx: LaunchContext, version: str) -> ContainerSpec:
    """Container efêmero que instala ou atualiza o jogo no volume."""
    branch = (version or BRANCH_PADRAO).strip()
    beta = "" if branch == BRANCH_PADRAO else f" -beta {branch}"
    comando = (
        f"set -e; {_STEAMCMD} +force_install_dir {INSTALL_DIR} "
        f"+login anonymous +app_update {STEAM_APP_ID}{beta} validate +quit"
    )
    return ContainerSpec(
        image=IMAGE,
        # HOME explícito porque rodamos com uid numérico: nesse caso o Docker
        # não lê o /etc/passwd do container, e o SteamCMD sem HOME não acha
        # onde gravar a própria configuração ("Missing configuration").
        env={"HOME": HOME_STEAM},
        command=["bash", "-c", comando],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        run_as=RUN_AS,
    )


def install_disk_bytes(version: str) -> int:
    return DISCO_NECESSARIO


def versions_spec() -> ContainerSpec:
    """Container efêmero que pergunta à Steam quais versões existem."""
    return ContainerSpec(
        image=IMAGE,
        env={"HOME": HOME_STEAM},
        command=[
            "bash",
            "-c",
            f"{_STEAMCMD} +login anonymous +app_info_print {STEAM_APP_ID} +quit",
        ],
        run_as=RUN_AS,
    )


def parse_versions(stdout: str) -> list[VersionInfo]:
    """Lê as branches do dump do SteamCMD.

    Degrada para lista vazia em vez de levantar: Steam fora do ar não pode
    impedir a tela de criação de abrir.
    """
    bloco = _BLOCO_BRANCHES.search(stdout or "")
    if not bloco:
        return []

    texto = bloco.group(1)
    versoes: list[VersionInfo] = []
    marcas = list(_BRANCH.finditer(texto))
    for i, m in enumerate(marcas):
        nome = m.group(1)
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        campos = dict(_CAMPO.findall(texto[m.end() : fim]))
        descricao = campos.get("description", "")
        instavel = "experimental" in nome or "unstable" in descricao.lower()
        versoes.append(
            VersionInfo(
                id=nome,
                label="Mais recente (estável)" if nome == BRANCH_PADRAO else nome,
                description=descricao,
                build=campos.get("buildid", ""),
                stable=not instavel,
            )
        )
    return versoes


def installed_version(root_dir: Path) -> str:
    """Build instalado, lido do manifesto que o próprio SteamCMD mantém."""
    manifesto = Path(root_dir) / "server" / "steamapps" / f"appmanifest_{STEAM_APP_ID}.acf"
    try:
        texto = manifesto.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r'"buildid"\s+"(\d+)"', texto)
    return m.group(1) if m else ""
