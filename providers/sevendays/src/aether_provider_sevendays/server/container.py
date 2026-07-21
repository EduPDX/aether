"""Container que roda o servidor de 7 Days to Die.

A escolha da imagem é deliberada: ``cm2network/steamcmd`` em vez de uma imagem
pronta de 7DTD (LinuxGSM etc.). O motivo é arquitetural — as prontas escondem
servidor, config e saves em caminhos próprios e administram via telnet, o que
quebraria os módulos de config, arquivos e backup do Aether. Aqui tudo mora no
volume ``/data`` (a raiz da instância) e o binário roda com stdout/stdin
ligados ao Core, como qualquer outra instância.

A instalação **não** acontece aqui: ela é uma fase própria (``install.py``),
o que deixa a subida do servidor rápida e permite escolher versão, preparar a
configuração a partir do que o jogo distribui e atualizar sob controle.
"""

from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, PortMapping, VolumeMount
from aether_sdk.steamcmd import IMAGE, INSTALL_DIR, RUN_AS

from aether_provider_sevendays.server.serverconfig import CONFIG_FILE, SERVERCONFIG_SCHEMA

DEFAULT_PORT = 26900
BINARIO = "7DaysToDieServer.x86_64"

# -logfile é omitido de propósito: com ele o Unity silencia o stdout e o
# console do painel ficaria vazio.
_BOOT = (
    f"set -e; cd {INSTALL_DIR}; "
    f"exec ./{BINARIO} -quit -batchmode -nographics -dedicated "
    f"-configfile=/data/{CONFIG_FILE}"
)


def build_container_spec(ctx: LaunchContext) -> ContainerSpec | None:
    """``None`` enquanto o servidor não foi instalado — sem os arquivos do
    jogo não há o que subir, e o erro fica claro em vez de um container que
    morre com 'no such file'."""
    if not (Path(ctx.root_dir) / "server" / BINARIO).is_file():
        return None

    cfg = dict(ctx.provider_data.get("container") or {})
    porta = int(cfg.get("port") or DEFAULT_PORT)
    return ContainerSpec(
        image=IMAGE,
        env={},
        command=["bash", "-c", _BOOT],
        ports=[
            PortMapping(container_port=DEFAULT_PORT, protocol="tcp", host_port=porta),
            PortMapping(container_port=DEFAULT_PORT, protocol="udp", host_port=porta),
            # Steam networking usa as duas seguintes; sem elas o servidor
            # existe mas não aparece na lista nem aceita NAT punch.
            PortMapping(container_port=26901, protocol="udp", host_port=porta + 1),
            PortMapping(container_port=26902, protocol="udp", host_port=porta + 2),
        ],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        run_as=RUN_AS,
        stop_command="shutdown",
    )


def provision_schema():
    """Criar servidor = escolher o essencial do serverconfig.

    Mesmo schema da tela de Config, sem os campos avançados: o resto tem
    padrão bom e pode ser ajustado depois, com o arquivo do jogo já em disco.
    """
    schema = SERVERCONFIG_SCHEMA.model_copy(deep=True)
    schema.id = "sevendays-provision"
    schema.label = "Novo servidor 7 Days to Die"
    schema.fields = [f for f in schema.fields if not f.advanced]
    return schema


def provision(root_dir: Path, values: dict) -> dict:
    """Guarda as escolhas do usuário; o arquivo de config só nasce depois.

    Não dá para escrever o serverconfig.xml agora: ele precisa ser uma cópia
    do arquivo da versão que ainda vai ser instalada. As respostas ficam
    guardadas e são aplicadas pelo ``after_install``.
    """
    (root_dir / "server").mkdir(exist_ok=True)
    (root_dir / "UserData").mkdir(exist_ok=True)
    return {
        "container": {"port": DEFAULT_PORT},
        "pending_config": {k: str(v) for k, v in values.items()},
    }
