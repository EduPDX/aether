"""SteamCMD: infraestrutura comum a todo servidor dedicado baixado da Steam.

Três providers já baixam o servidor por SteamCMD (7 Days to Die, Satisfactory,
HumanitZ) e a receita é sempre a mesma: um container efêmero roda o
``steamcmd.sh``, autentica anônimo e faz ``app_update`` do app dedicado no
volume da instância. Manter isso num só lugar evita que cada provider carregue
sua cópia das armadilhas abaixo — e são armadilhas que já custaram depuração:

- apps de servidor dedicado são do tipo *Tool*, e para esses o SteamCMD não
  resolve a plataforma sozinho: sem ``+@sSteamCmdForcePlatformType linux``
  **antes** do ``+login`` ele aborta com "Missing configuration" sem baixar
  nada. A flag é inofensiva para apps normais, então entra sempre;
- ele recusa rodar como root ("Missing file permissions"), daí ``RUN_AS``;
- rodando com uid numérico o Docker não lê o ``/etc/passwd`` do container, e o
  SteamCMD sem ``HOME`` não acha onde gravar a própria config — daí ``HOME``
  explícito no ambiente.

O que muda de um jogo para outro é só o **app id**, a **branch** e onde o
binário do servidor mora — nada disso é responsabilidade do Core.
"""

import re
from pathlib import Path

from aether_sdk.container import ContainerSpec, VolumeMount
from aether_sdk.install import VersionInfo

IMAGE = "cm2network/steamcmd:root"
"""Imagem só com o SteamCMD; o binário do jogo vem no volume, não na imagem."""

RUN_AS = "1000:1000"
"""O SteamCMD (e o servidor, que herda o mesmo uid) não rodam como root."""

HOME_STEAM = "/home/steam"
INSTALL_DIR = "/data/server"
"""Onde os arquivos do jogo ficam dentro do volume ``/data`` da instância."""

DEFAULT_BRANCH = "public"

_STEAMCMD = f"{HOME_STEAM}/steamcmd/steamcmd.sh +@sSteamCmdForcePlatformType linux"

# O dump do `app_info_print` é um VDF aninhado. Só o bloco "branches" interessa,
# e dentro dele cada chave no nível certo de indentação é uma branch.
_BLOCO_BRANCHES = re.compile(r'"branches"\s*\{(.*)', re.DOTALL)
_BRANCH = re.compile(r'^\t{3}"([^"]+)"\s*$', re.MULTILINE)
_CAMPO = re.compile(r'^\t{4}"(buildid|description)"\s+"([^"]*)"', re.MULTILINE)


def install_spec(app_id: int, version: str, *, install_dir: str = INSTALL_DIR) -> ContainerSpec:
    """Container efêmero que instala ou atualiza o jogo no volume.

    ``version`` é uma branch da Steam. A branch padrão se pede pela **ausência**
    de ``-beta`` — ``-beta public`` não é aceito pelo SteamCMD.
    """
    branch = (version or DEFAULT_BRANCH).strip()
    beta = "" if branch == DEFAULT_BRANCH else f" -beta {branch}"
    comando = (
        f"set -e; {_STEAMCMD} +force_install_dir {install_dir} "
        f"+login anonymous +app_update {app_id}{beta} validate +quit"
    )
    return ContainerSpec(
        image=IMAGE,
        env={"HOME": HOME_STEAM},
        command=["bash", "-c", comando],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        run_as=RUN_AS,
    )


def versions_spec(app_id: int) -> ContainerSpec:
    """Container efêmero que pergunta à Steam quais branches existem."""
    return ContainerSpec(
        image=IMAGE,
        env={"HOME": HOME_STEAM},
        command=[
            "bash",
            "-c",
            f"{_STEAMCMD} +login anonymous +app_info_print {app_id} +quit",
        ],
        run_as=RUN_AS,
    )


def parse_branches(stdout: str) -> list[VersionInfo]:
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
        instavel = (
            "experimental" in nome
            or "beta" in nome
            or "unstable" in descricao.lower()
            or "experimental" in descricao.lower()
        )
        versoes.append(
            VersionInfo(
                id=nome,
                label="Mais recente (estável)" if nome == DEFAULT_BRANCH else nome,
                description=descricao,
                build=campos.get("buildid", ""),
                stable=not instavel,
            )
        )
    return versoes


def installed_build(root_dir: Path, app_id: int, *, server_subdir: str = "server") -> str:
    """Build instalado, lido do manifesto que o próprio SteamCMD mantém.

    Vazio quando nada foi instalado — é o sinal de que não há o que subir.
    """
    manifesto = Path(root_dir) / server_subdir / "steamapps" / f"appmanifest_{app_id}.acf"
    try:
        texto = manifesto.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r'"buildid"\s+"(\d+)"', texto)
    return m.group(1) if m else ""
