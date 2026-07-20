"""Runtime containerizado do Minecraft: spec e criação de servidor do zero.

Usa a imagem ``itzg/minecraft-server`` — o padrão de facto da comunidade —
porque ela resolve por env o que exigiria instalador próprio: baixar a versão,
instalar Forge/Fabric/Paper, aceitar a EULA e ajustar a memória da JVM. O
provider vira só uma tradução de formulário → variáveis de ambiente.
"""

from pathlib import Path

from aether_sdk import (
    ConfigField,
    ConfigFieldType,
    ConfigSchema,
    ContainerSpec,
    LaunchContext,
    PortMapping,
    VolumeMount,
)

IMAGE = "itzg/minecraft-server"
DEFAULT_PORT = 25565

PROVISION_SCHEMA = ConfigSchema(
    id="minecraft-provision",
    label="Novo servidor Minecraft",
    file="",  # não há arquivo: as respostas viram env do container
    format="provision",
    fields=[
        ConfigField(
            key="type",
            label="Tipo de servidor",
            type=ConfigFieldType.ENUM,
            options=["VANILLA", "FORGE", "FABRIC", "PAPER"],
            default="VANILLA",
            description="Loader que o servidor usa; define como mods/plugins são carregados.",
        ),
        ConfigField(
            key="version",
            label="Versão do Minecraft",
            default="LATEST",
            description="Ex.: 1.20.1 — ou LATEST para a mais recente.",
        ),
        ConfigField(
            key="memory",
            label="Memória da JVM",
            default="4G",
            description="Quanto o Java pode usar (ex.: 2G, 6G).",
        ),
        ConfigField(
            key="port",
            label="Porta",
            type=ConfigFieldType.INTEGER,
            default=str(DEFAULT_PORT),
            minimum=1024,
            maximum=65535,
        ),
        ConfigField(
            key="eula",
            label="Aceito a EULA do Minecraft (minecraft.net/eula)",
            type=ConfigFieldType.BOOLEAN,
            default="false",
            description="O servidor não inicia sem o aceite.",
        ),
    ],
)


def provision(root_dir: Path, values: dict) -> dict:
    """Valida o formulário e devolve o provider_data inicial.

    Nada é escrito em disco de propósito: a imagem popula o volume ``/data``
    na primeira subida, e é ela quem entende o layout que criou.
    """
    aceite = str(values.get("eula", "")).lower() in ("true", "1", "yes")
    if not aceite:
        raise ValueError("a EULA do Minecraft precisa ser aceita para criar o servidor")
    porta = int(values.get("port") or DEFAULT_PORT)
    return {
        "container": {
            "type": str(values.get("type") or "VANILLA").upper(),
            "version": str(values.get("version") or "LATEST"),
            "memory": str(values.get("memory") or "4G"),
            "port": porta,
            "eula": True,
        }
    }


def build_container_spec(ctx: LaunchContext) -> ContainerSpec | None:
    """Monta o spec a partir do ``provider_data.container``.

    Sem provision (pasta adotada movida para Docker) os defaults valem, mas a
    EULA fica em FALSE — o container sobe, avisa e para, que é o comportamento
    honesto: aceite de licença não se presume.
    """
    cfg = dict(ctx.provider_data.get("container") or {})
    porta = int(cfg.get("port") or DEFAULT_PORT)
    env = {
        "EULA": "TRUE" if cfg.get("eula") else "FALSE",
        "TYPE": str(cfg.get("type") or "VANILLA"),
        "VERSION": str(cfg.get("version") or "LATEST"),
        "MEMORY": str(cfg.get("memory") or "4G"),
        # Sem TTY o console interativo da imagem viraria eco infinito;
        # o stdin continua chegando ao processo java para comandos.
        "EXEC_DIRECTLY": "true",
    }
    return ContainerSpec(
        image=IMAGE,
        env=env,
        ports=[PortMapping(container_port=DEFAULT_PORT, protocol="tcp", host_port=porta)],
        volumes=[VolumeMount(container_path="/data", subdir=".")],
        stop_command="stop",
    )
