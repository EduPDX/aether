"""Container que roda o servidor dedicado de HumanitZ.

Mesma decisão dos outros providers Steam: imagem ``cm2network/steamcmd`` e o
binário do jogo no volume ``/data``, com a instalação como fase própria. A
configuração de jogo mora em ``GameServerSettings.ini`` e é editável pelo painel
(ver ``serversettings.py``).
"""

from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, PortMapping
from aether_sdk.container import VolumeMount
from aether_sdk.steamcmd import IMAGE, INSTALL_DIR, RUN_AS

from aether_provider_humanitz.server.serversettings import SETTINGS_SCHEMA

DEFAULT_PORT = 7777
DEFAULT_QUERY_PORT = 27015
LAUNCHER = "HumanitZServer.sh"

# O nome de query da Steam vai por variável de ambiente para não esbarrar em
# aspas no shell; -queryport habilita o protocolo de consulta (ping/lista).
_BOOT = (
    f"set -e; cd {INSTALL_DIR}; "
    f'exec ./{LAUNCHER} -log -port="$AETHER_PORT" -queryport="$AETHER_QUERY_PORT" '
    f'-steamservername="$AETHER_STEAM_NAME"'
)


def build_container_spec(ctx: LaunchContext) -> ContainerSpec | None:
    """``None`` enquanto o servidor não foi instalado — sem os arquivos do jogo
    não há o que subir."""
    if not (Path(ctx.root_dir) / "server" / LAUNCHER).is_file():
        return None

    cfg = dict(ctx.provider_data.get("container") or {})
    porta = int(cfg.get("port") or DEFAULT_PORT)
    query = int(cfg.get("query_port") or DEFAULT_QUERY_PORT)
    return ContainerSpec(
        image=IMAGE,
        env={
            "AETHER_PORT": str(porta),
            "AETHER_QUERY_PORT": str(query),
            "AETHER_STEAM_NAME": str(cfg.get("steam_name") or "HumanitZ"),
        },
        command=["bash", "-c", _BOOT],
        ports=[
            PortMapping(container_port=DEFAULT_PORT, protocol="udp", host_port=porta),
            PortMapping(container_port=DEFAULT_QUERY_PORT, protocol="udp", host_port=query),
        ],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        run_as=RUN_AS,
    )


def provision_schema():
    """Criar servidor = escolher o essencial do GameServerSettings.

    Mesmo schema da tela de Config, sem os campos avançados: o resto tem padrão
    bom e pode ser ajustado depois, com o arquivo do jogo já em disco.
    """
    schema = SETTINGS_SCHEMA.model_copy(deep=True)
    schema.id = "humanitz-provision"
    schema.label = "Novo servidor HumanitZ"
    # Aqui o arquivo ainda não existe (o jogo nem foi baixado), então não dá
    # para esconder campos pelo arquivo — mostram-se todos os não avançados.
    schema.fields_from_file = False
    schema.fields = [f for f in schema.fields if not f.advanced]
    return schema


def provision(root_dir: Path, values: dict) -> dict:
    """Guarda as escolhas do usuário; o GameServerSettings.ini só nasce depois.

    Ele precisa ser uma cópia do arquivo de referência da versão instalada, e
    nessa hora o jogo ainda não existe em disco. As respostas ficam pendentes
    até o ``after_install``.
    """
    (root_dir / "server").mkdir(exist_ok=True)
    return {
        "container": {
            "port": DEFAULT_PORT,
            "query_port": DEFAULT_QUERY_PORT,
            # O nome que aparece no navegador da Steam segue o nome do servidor.
            "steam_name": str(values.get("ServerName") or "HumanitZ"),
        },
        "pending_config": {k: str(v) for k, v in values.items()},
    }
