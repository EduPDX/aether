"""Contrato de mapa-mundi: servir uma visão web do mundo da instância.

Ver a evolução do mundo num navegador é conhecimento do jogo: qual ferramenta
gera o mapa, onde ficam os arquivos do mundo, em que porta a interface é
servida. O Core sabe *como* rodar e publicar isso — e a decisão de peso,
registrada no ADR, é rodar o mapa como um **container à parte (sidecar)**, lendo
o mundo por volume compartilhado, para o render nunca disputar CPU com o jogo.

Só o provider de Minecraft implementa isto hoje (BlueMap). O contrato existe
para que o próximo jogo com mapa web se encaixe implementando um protocolo, sem
tocar no Core nem no painel.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from aether_sdk.container import ContainerSpec
from aether_sdk.launch import LaunchContext


@dataclass(frozen=True)
class MapSeedFile:
    """Arquivo de configuração que o Core grava antes de subir o mapa.

    ``path`` é relativo ao ``root_dir`` da instância. É assim que o provider
    entrega a config do gerador de mapa (aceitar ler o mundo, limitar as
    threads de render, apontar a porta) sem que o Core conheça o formato — ele
    só materializa os bytes no lugar certo, e o volume do container os monta.
    """

    path: str
    content: str
    #: Não sobrescrever se o arquivo já existir — assim o dono do servidor pode
    #: ajustar a config à mão depois sem o próximo "Ativar mapa" desfazer.
    keep_existing: bool = True


@dataclass(frozen=True)
class MapPlan:
    """Como servir o mapa web de uma instância, como sidecar.

    O ``container`` é um :class:`ContainerSpec` comum — o Core o cria e sobe
    pela mesma camada de runtime que roda o servidor do jogo, então nenhuma
    infraestrutura nova aparece para quem instala o Aether. Os volumes do spec
    devem montar o mundo (só-leitura) e a pasta de dados do mapa; ``web_port``
    diz qual porta do container serve a interface, para o Core publicá-la e
    derivar a URL.
    """

    container: ContainerSpec
    #: Porta interna onde a UI do mapa é servida — o Core publica e monta a URL.
    web_port: int
    #: Caminho da UI sob o host (o BlueMap serve na raiz).
    url_path: str = "/"
    #: Configs a gravar antes do primeiro boot do container do mapa.
    seed_files: tuple[MapSeedFile, ...] = field(default_factory=tuple)


@runtime_checkable
class SupportsMap(Protocol):
    """Provider que sabe servir um mapa web do mundo da sua instância."""

    def map_plan(self, ctx: LaunchContext) -> MapPlan | None:
        """Plano do sidecar de mapa, ou ``None`` quando ainda não dá para
        servir (mundo não gerado, versão sem suporte).

        O Core traduz o plano em: gravar as ``seed_files``, criar e subir o
        ``container`` pela camada de runtime, publicar a ``web_port`` e guardar
        o estado (ligado/porta/URL) no ``provider_data`` da instância.
        """
        ...
