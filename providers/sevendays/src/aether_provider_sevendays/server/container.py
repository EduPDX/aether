"""Container do 7 Days to Die: SteamCMD instala, o binário roda em foreground.

A escolha da imagem é deliberada: ``cm2network/steamcmd:root`` em vez de uma
imagem pronta de 7DTD (LinuxGSM etc.). O motivo é arquitetural — as imagens
prontas escondem servidor, config e saves em caminhos próprios e administram
via telnet, o que quebraria os módulos de config, files e backup do Aether.
Aqui tudo mora no volume ``/data`` (a raiz da instância): o SteamCMD valida a
instalação a cada subida e o binário roda com stdout/stdin ligados ao Core,
como qualquer outra instância.
"""

from pathlib import Path

from aether_sdk import ContainerSpec, LaunchContext, PortMapping, VolumeMount

from aether_provider_sevendays.server.serverconfig import (
    CONFIG_FILE,
    SERVERCONFIG_SCHEMA,
    render_initial_config,
)

IMAGE = "cm2network/steamcmd:root"
STEAM_APP_ID = 294420
DEFAULT_PORT = 26900

# O SteamCMD recusa rodar como root ("Missing file permissions") — a imagem
# traz o usuário `steam` justamente para isso.
RUN_AS = "1000:1000"

# `+@sSteamCmdForcePlatformType linux` vem ANTES do login e não é opcional: o
# 294420 é um app do tipo "Tool", e para esses o SteamCMD não resolve a
# plataforma sozinho — aborta com "Missing configuration" sem baixar nada.
#
# -logfile é omitido de propósito: com ele o Unity silencia o stdout e o
# console do painel ficaria vazio.
_BOOT = (
    "set -e; "
    "/home/steam/steamcmd/steamcmd.sh +@sSteamCmdForcePlatformType linux "
    f"+force_install_dir /data/server "
    f"+login anonymous +app_update {STEAM_APP_ID} validate +quit; "
    "cd /data/server; "
    "exec ./7DaysToDieServer.x86_64 -quit -batchmode -nographics -dedicated "
    f"-configfile=/data/{CONFIG_FILE}"
)


def build_container_spec(ctx: LaunchContext) -> ContainerSpec | None:
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
    """Criar servidor = preencher o serverconfig inicial; o schema é o mesmo
    da tela de config, sem os campos avançados."""
    schema = SERVERCONFIG_SCHEMA.model_copy(deep=True)
    schema.id = "sevendays-provision"
    schema.label = "Novo servidor 7 Days to Die"
    schema.fields = [f for f in schema.fields if not f.advanced]
    return schema


def provision(root_dir: Path, values: dict) -> dict:
    (root_dir / CONFIG_FILE).write_text(render_initial_config(values), encoding="utf-8")
    (root_dir / "server").mkdir(exist_ok=True)
    (root_dir / "UserData").mkdir(exist_ok=True)
    return {"container": {"port": DEFAULT_PORT}}
