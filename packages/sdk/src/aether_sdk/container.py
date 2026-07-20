"""Contrato de container (v0.3): como um provider descreve um servidor containerizado.

O provider nunca fala com o Docker: ele traduz a instância num
:class:`ContainerSpec` declarativo (imagem, env, portas, volumes) e o Core
executa através da sua camada de abstração de runtime. Isso mantém regra de
jogo fora da infraestrutura — adicionar um jogo novo é escrever um provider,
não mexer no Core.

O contrato de criação (:class:`SupportsProvision`) existe porque instância
containerizada nasce do zero: não há pasta pré-existente para adotar, então o
provider precisa dizer que perguntas fazer (schema) e como materializar os
arquivos iniciais a partir das respostas.
"""

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from aether_sdk.config import ConfigSchema
from aether_sdk.launch import ConsoleCodec, LaunchContext


class PortMapping(BaseModel):
    """Uma porta exposta pelo servidor dentro do container.

    ``host_port`` é a sugestão padrão do provider; a instância pode
    sobrescrever via ``provider_data`` sem tocar no contrato.
    """

    container_port: int
    protocol: Literal["tcp", "udp"] = "tcp"
    host_port: int | None = None


class VolumeMount(BaseModel):
    """Bind mount do diretório da instância para dentro do container.

    ``subdir`` é relativo ao ``root_dir`` da instância (``"."`` monta a
    raiz inteira) — assim backup, files e content continuam enxergando os
    mesmos arquivos que o servidor usa.
    """

    container_path: str
    subdir: str = "."


class ContainerSpec(BaseModel):
    """Um servidor containerizado pronto para o Core criar e subir."""

    image: str
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[PortMapping] = Field(default_factory=list)
    volumes: list[VolumeMount] = Field(default_factory=list)
    command: list[str] | None = None
    run_as: str = ""
    """Usuário do container no formato ``uid:gid`` quando o servidor recusa
    rodar como root (o SteamCMD, por exemplo, aborta com "Missing file
    permissions"). O Core ajusta o dono dos volumes para este uid."""
    stop_command: str | None = None
    """Texto escrito no stdin do container para parada graciosa; ``None``
    significa parar por sinal."""
    stop_signal: str = "SIGTERM"


@runtime_checkable
class SupportsContainer(Protocol):
    """Capacidade opcional: rodar o servidor da instância em container.

    ``container_spec`` devolve ``None`` quando a instância não tem o que é
    preciso para containerizar (ex.: provision nunca rodou).
    """

    def container_spec(self, ctx: LaunchContext) -> ContainerSpec | None: ...

    def console_codec(self) -> ConsoleCodec: ...


@runtime_checkable
class SupportsProvision(Protocol):
    """Capacidade opcional: criar um servidor novo do zero.

    ``provision`` escreve os arquivos iniciais em ``root_dir`` (um diretório
    vazio gerenciado pelo Core) e devolve o ``provider_data`` inicial da
    instância — é aqui que mora, por exemplo, o aceite de EULA ou a escrita
    do arquivo de configuração inicial.
    """

    def provision_schema(self) -> ConfigSchema: ...

    def provision(self, root_dir: Path, values: dict) -> dict: ...
