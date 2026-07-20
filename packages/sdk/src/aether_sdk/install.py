"""Contrato de instalação (v0.4): baixar, escolher versão e atualizar.

Separar a instalação da execução resolve três coisas que ficavam impossíveis
quando o download acontecia dentro do boot do servidor: escolher a versão,
preparar a configuração a partir dos arquivos recém-instalados, e atualizar
sob controle (com backup antes).

O Core roda um container efêmero até o fim e devolve a saída ao provider —
é o provider que sabe ler o que o instalador do seu jogo imprime. Assim
nenhuma noção de Steam, de repositório ou de loja entra no Core.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from aether_sdk.container import ContainerSpec
from aether_sdk.launch import LaunchContext


class VersionInfo(BaseModel):
    """Uma versão instalável do servidor."""

    id: str
    """Identificador que volta em ``install_spec`` (uma branch, uma tag)."""
    label: str
    description: str = ""
    build: str = ""
    """Build da versão, quando existe — serve para comparar o que está no
    disco com o que a origem oferece."""
    stable: bool = True
    """Versões instáveis aparecem separadas: entrar numa experimental sem
    querer é uma forma comum de quebrar um servidor em produção."""


@runtime_checkable
class SupportsInstall(Protocol):
    """Capacidade opcional: o servidor é instalado e atualizado pelo painel.

    Providers cuja imagem já resolve a instalação sozinha (o Minecraft via
    ``itzg``, por exemplo) simplesmente não implementam este contrato — e o
    painel não oferece as telas de versão.
    """

    def install_spec(self, ctx: LaunchContext, version: str) -> ContainerSpec:
        """Container efêmero que instala/atualiza o servidor no volume."""
        ...

    def versions_spec(self) -> ContainerSpec | None:
        """Container efêmero que lista as versões disponíveis na origem.

        ``None`` quando o provider resolve a lista sem rede.
        """
        ...

    def parse_versions(self, stdout: str) -> list[VersionInfo]:
        """Lê a saída de ``versions_spec``. Deve degradar para lista vazia em
        vez de levantar: origem fora do ar não pode quebrar a tela."""
        ...

    def installed_version(self, root_dir: Path) -> str:
        """O que está instalado no disco; vazio quando nada foi instalado."""
        ...

    def after_install(self, root_dir: Path, provider_data: dict) -> dict:
        """Roda após uma instalação bem-sucedida, com os arquivos no disco.

        É onde o provider prepara a configuração a partir do que o jogo
        distribui — o único momento em que ela existe para ser lida. Devolve
        as mudanças a mesclar no ``provider_data`` da instância.
        """
        ...


class InstallResult(BaseModel):
    """Resultado de uma instalação, para a interface contar o que houve."""

    version: str
    build: str = ""
    config_seeded: bool = False
    """A configuração foi criada agora a partir do arquivo do jogo."""
    new_properties: list[str] = Field(default_factory=list)
    """Propriedades que a versão nova trouxe e foram acrescentadas à
    configuração existente, preservando o que o usuário já tinha."""
