"""Container que roda o servidor dedicado de Satisfactory.

Mesma decisão dos outros providers Steam: a imagem é o ``cm2network/steamcmd``
e o binário do jogo vem no volume ``/data``, para que config, arquivos e backup
enxerguem os mesmos arquivos que o servidor usa. A instalação é fase própria
(``install.py``), então o boot é rápido e não fala com a Steam.

Satisfactory é um caso particular: **não há configuração de servidor em
arquivo**. Nome, senha e regras de jogo são definidos dentro do próprio jogo,
depois que o cliente se conecta e reivindica o servidor. Por isso este provider
não implementa ``SupportsConfig`` e o provisionamento não pede nada além do
nome da instância — o resto acontece no jogo.
"""

from pathlib import Path

from aether_sdk import ConfigSchema, ContainerSpec, LaunchContext, PortMapping
from aether_sdk.container import VolumeMount
from aether_sdk.steamcmd import IMAGE, INSTALL_DIR, RUN_AS

# Desde a 1.0 o Satisfactory usa uma única porta (7777) para TCP e UDP; as
# antigas BeaconPort/ServerQueryPort deixaram de ser necessárias.
DEFAULT_PORT = 7777
LAUNCHER = "FactoryServer.sh"

_BOOT = f'set -e; cd {INSTALL_DIR}; exec ./{LAUNCHER} -Port="$AETHER_PORT" -log -unattended'


def build_container_spec(ctx: LaunchContext) -> ContainerSpec | None:
    """``None`` enquanto o servidor não foi instalado — sem os arquivos do jogo
    não há o que subir, e o erro fica claro em vez de um container que morre com
    'no such file'."""
    if not (Path(ctx.root_dir) / "server" / LAUNCHER).is_file():
        return None

    cfg = dict(ctx.provider_data.get("container") or {})
    porta = int(cfg.get("port") or DEFAULT_PORT)
    return ContainerSpec(
        image=IMAGE,
        env={"AETHER_PORT": str(porta)},
        command=["bash", "-c", _BOOT],
        ports=[
            PortMapping(container_port=DEFAULT_PORT, protocol="tcp", host_port=porta),
            PortMapping(container_port=DEFAULT_PORT, protocol="udp", host_port=porta),
        ],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        run_as=RUN_AS,
        # O launcher repassa SIGINT ao binário, que salva e sai; é o que a
        # unit do próprio jogo usa (KillSignal=SIGINT).
        stop_signal="SIGINT",
    )


def provision_schema() -> ConfigSchema:
    """Satisfactory não tem configuração de servidor em arquivo: nome, senha e
    regras são definidos no jogo depois de reivindicar o servidor. O schema fica
    vazio de propósito — a interface mostra que não há nada a preencher aqui."""
    return ConfigSchema(
        id="satisfactory-provision",
        label="Novo servidor Satisfactory",
        file="",
        fields=[],
    )


def provision(root_dir: Path, values: dict) -> dict:
    """Cria a pasta do servidor e guarda a porta padrão. Não há config a
    escrever: o servidor é configurado dentro do jogo."""
    (root_dir / "server").mkdir(exist_ok=True)
    return {"container": {"port": DEFAULT_PORT}, "pending_config": {}}
