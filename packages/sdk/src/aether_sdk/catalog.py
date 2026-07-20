"""Catálogo de jogos: o que o painel mostra antes de criar um servidor.

Quem escolhe hospedar um jogo precisa saber o que vai precisar — RAM por
número de jogadores, portas a liberar, se roda em Linux — e nada disso está
numa loja de jogos. Essas respostas são conhecimento de **hospedagem**, então
moram no provider, que é quem sabe rodar aquele servidor.

O que uma fonte externa sabe (descrição, gênero, desenvolvedora, requisitos da
Steam, imagens) entra por cima, como enriquecimento. É por isso que o contrato
separa os dois: um jogo fora da Steam — o Minecraft, por exemplo — continua com
uma página completa, só sem a parte enriquecida.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class RequisitosDeHardware(BaseModel):
    """Um conjunto de requisitos (mínimo ou recomendado)."""

    cpu: str = ""
    ram: str = ""
    disco: str = ""
    rede: str = ""
    observacao: str = ""


class RamPorJogadores(BaseModel):
    """Quanta memória reservar para uma faixa de jogadores.

    A pergunta que todo mundo faz antes de subir um servidor, e que nenhuma
    página de loja responde.
    """

    ate_jogadores: int
    ram: str
    observacao: str = ""


class PortaDoJogo(BaseModel):
    numero: int
    protocolo: str = "tcp"
    descricao: str = ""
    obrigatoria: bool = True


class LinkUtil(BaseModel):
    titulo: str
    url: str


class GameCatalogEntry(BaseModel):
    """A ficha de um jogo, do ponto de vista de quem vai hospedá-lo."""

    id: str
    """Identificador estável do jogo; casa com o provider que sabe rodá-lo."""
    provider_id: str
    nome: str
    tagline: str = ""
    descricao: str = ""
    genero: list[str] = Field(default_factory=list)
    desenvolvedora: str = ""
    publicadora: str = ""
    plataformas_do_cliente: list[str] = Field(default_factory=list)
    so_do_servidor: list[str] = Field(default_factory=list)

    logo_url: str = ""
    banner_url: str = ""
    atribuicao_da_imagem: str = ""
    """Crédito exigido pela licença da imagem, quando houver.

    Existe porque nem toda imagem livre é livre de obrigações: a do Minecraft é
    CC BY, que pede atribuição. Guardar isso junto da URL é o que garante que o
    crédito apareça onde a imagem aparece."""

    requisitos_servidor_minimo: RequisitosDeHardware | None = None
    requisitos_servidor_recomendado: RequisitosDeHardware | None = None
    requisitos_cliente_minimo: RequisitosDeHardware | None = None
    requisitos_cliente_recomendado: RequisitosDeHardware | None = None

    ram_por_jogadores: list[RamPorJogadores] = Field(default_factory=list)
    portas: list[PortaDoJogo] = Field(default_factory=list)
    observacoes_de_hospedagem: list[str] = Field(default_factory=list)
    links: list[LinkUtil] = Field(default_factory=list)

    steam_app_id: int | None = None
    """App da **loja**, não o do servidor dedicado.

    No 7 Days to Die são diferentes: 251570 tem página na loja, 294420 é a
    ferramenta de servidor e não tem — pedir metadados do 294420 volta vazio.
    """


@runtime_checkable
class SupportsCatalog(Protocol):
    """Capacidade opcional: o provider descreve o jogo para o catálogo.

    Sem isto o jogo ainda funciona; ele só não ganha página própria, aparecendo
    apenas com o nome do manifest.
    """

    def catalog_entry(self) -> GameCatalogEntry: ...
