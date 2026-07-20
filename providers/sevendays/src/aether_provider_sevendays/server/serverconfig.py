"""serverconfig.xml: schema de configuração e codec XML.

A base é sempre o arquivo que o **jogo distribui**, nunca um arquivo gerado
por nós. O motivo é que o conjunto de propriedades muda de versão para versão
— a 3.0 tirou ``GameDifficulty`` e ``DayNightLength`` e pôs o sistema
``SandboxCode`` no lugar. Um arquivo gerado a partir do que o painel conhece
ficaria sem as ~50 propriedades restantes e ainda escreveria opções que a
versão instalada ignora em silêncio.

Daí as três regras deste módulo:

- ``apply`` só substitui propriedade que já existe; nunca inventa;
- ``mesclar_novas`` traz para o arquivo da instância o que a versão nova
  passou a oferecer, preservando os valores do usuário;
- o que o painel não mapeia fica intocado — quem precisa mexer usa o editor
  bruto da interface.

O trabalho é por regex sobre o texto, e não por reescrita do XML, porque o
arquivo do jogo documenta cada propriedade num comentário ao lado dela. Um
parser XML normal descartaria justamente essa documentação.
"""

import re
from pathlib import Path
from xml.sax.saxutils import escape, unescape

from aether_sdk import ConfigField, ConfigFieldType, ConfigSchema

CONFIG_FILE = "serverconfig.xml"
"""Onde o config vive na raiz da instância (o do jogo fica em server/)."""
CONFIG_DISTRIBUIDO = "server/serverconfig.xml"

_PROP = re.compile(r'<property\s+name="([^"]+)"\s+value="([^"]*)"\s*/>')
_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)
_FECHO = re.compile(r"</ServerSettings>")


def _regioes_comentadas(texto: str) -> list[tuple[int, int]]:
    """Trechos entre ``<!--`` e ``-->``.

    O arquivo do jogo traz propriedades comentadas como exemplo — a
    ``UserDataFolder`` é uma delas. Sem isto o codec as leria como se
    estivessem valendo e devolveria ``UserDataFolder=absolute_path``.
    """
    return [m.span() for m in _COMENTARIO.finditer(texto)]


def _comentada(span: tuple[int, int], regioes: list[tuple[int, int]]) -> bool:
    return any(inicio <= span[0] < fim for inicio, fim in regioes)


def _ativas(texto: str):
    """Propriedades que de fato valem, com posição — comentadas ficam de fora."""
    regioes = _regioes_comentadas(texto)
    for m in _PROP.finditer(texto):
        if not _comentada(m.span(), regioes):
            yield m


def _escapar(valor: str) -> str:
    return escape(str(valor), {'"': "&quot;"})


class ServerConfigXmlCodec:
    """Lê e altera propriedades preservando comentários, ordem e formatação."""

    def parse(self, texto: str) -> dict[str, str]:
        # &quot; entra na tabela extra: o sax só desfaz &amp;/&lt;/&gt; por padrão.
        return {m.group(1): unescape(m.group(2), {"&quot;": '"'}) for m in _ativas(texto)}

    def apply(self, texto: str, values: dict[str, str]) -> str:
        """Substitui o valor das propriedades existentes.

        Chave que não existe no arquivo é **ignorada** de propósito: inserir
        uma propriedade que a versão instalada não conhece só polui o arquivo
        e dá a falsa impressão de que a configuração foi aplicada.
        """
        for key, value in values.items():
            alvo = next((m for m in _ativas(texto) if m.group(1) == key), None)
            if alvo is None:
                continue
            inicio, fim = alvo.span(2)
            texto = texto[:inicio] + _escapar(value) + texto[fim:]
        return texto


def garantir(texto: str, key: str, value: str) -> str:
    """Aplica a propriedade, criando-a quando não existir.

    Exceção consciente à regra de não inventar propriedade: alguns valores não
    são escolha do usuário nem do jogo, mas do ambiente — os saves precisam
    cair no volume montado ou morrem com o container. No arquivo distribuído a
    ``UserDataFolder`` vem comentada, então é este caminho que a cria.
    """
    alvo = next((m for m in _ativas(texto) if m.group(1) == key), None)
    if alvo is not None:
        inicio, fim = alvo.span(2)
        return texto[:inicio] + _escapar(value) + texto[fim:]
    return _FECHO.sub(
        f'\t<property name="{key}" value="{_escapar(value)}"/>\n</ServerSettings>',
        texto,
        count=1,
    )


def mesclar_novas(atual: str, distribuido: str) -> tuple[str, list[str]]:
    """Traz para o arquivo da instância as propriedades que a versão nova
    passou a oferecer, com o padrão e a documentação do jogo.

    Devolve o texto e os nomes acrescentados. Valores existentes nunca são
    tocados, e propriedades que sumiram da versão nova ficam onde estão: são
    inofensivas, e removê-las apagaria a configuração de quem voltar atrás.
    """
    existentes = {m.group(1) for m in _ativas(atual)}
    novas: list[str] = []
    linhas: list[str] = []
    for linha in distribuido.splitlines():
        m = _PROP.search(linha)
        # A propriedade comentada de exemplo (UserDataFolder) não entra.
        if not m or _comentada(m.span(), _regioes_comentadas(linha)):
            continue
        nome = m.group(1)
        if nome in existentes:
            continue
        novas.append(nome)
        linhas.append(linha.rstrip())

    if not linhas:
        return atual, []

    bloco = "\n".join(["", "\t<!-- Propriedades novas desta versão do jogo -->", *linhas, ""])
    return _FECHO.sub(bloco + "</ServerSettings>", atual, count=1), novas


# --------------------------------------------------------------------- schema

_STR = ConfigFieldType.STRING
_INT = ConfigFieldType.INTEGER
_BOOL = ConfigFieldType.BOOLEAN
_ENUM = ConfigFieldType.ENUM
_PWD = ConfigFieldType.PASSWORD

_SO_RWG = {"GameWorld": "RWG"}

SERVERCONFIG_SCHEMA = ConfigSchema(
    id="serverconfig",
    label="serverconfig.xml",
    file=CONFIG_FILE,
    format="xml",
    # A versão instalada decide o que existe: campos ausentes do arquivo somem
    # do formulário em vez de virar configuração que o jogo ignora.
    fields_from_file=True,
    fields=[
        # ------------------------------------------------------------ Servidor
        ConfigField(
            key="ServerName",
            label="Nome do servidor",
            section="Servidor",
            default="Aether Server",
            description="Aparece na lista de servidores do jogo.",
        ),
        ConfigField(
            key="ServerDescription",
            label="Descrição",
            section="Servidor",
            description="Mostrada junto do nome na lista de servidores.",
        ),
        ConfigField(
            key="ServerPassword",
            label="Senha",
            type=_PWD,
            section="Servidor",
            description="Vazio = qualquer um pode entrar.",
        ),
        ConfigField(
            key="ServerMaxPlayerCount",
            label="Máximo de jogadores",
            type=_INT,
            default="8",
            minimum=1,
            maximum=64,
            section="Servidor",
        ),
        ConfigField(
            key="ServerVisibility",
            label="Visibilidade",
            type=_ENUM,
            options=["2", "1", "0"],
            default="2",
            section="Servidor",
            description="2 = pública, 1 = só amigos, 0 = fora da lista.",
        ),
        ConfigField(
            key="Region",
            label="Região",
            type=_ENUM,
            options=[
                "NorthAmericaEast",
                "NorthAmericaWest",
                "CentralAmerica",
                "SouthAmerica",
                "Europe",
                "Russia",
                "Asia",
                "MiddleEast",
                "Africa",
                "Oceania",
            ],
            default="SouthAmerica",
            section="Servidor",
            description="Usada pelo jogo para agrupar servidores na busca.",
        ),
        ConfigField(
            key="Language",
            label="Idioma",
            default="Portuguese",
            section="Servidor",
            description="Nome do idioma em inglês, como os jogadores procurariam.",
        ),
        ConfigField(
            key="ServerWebsiteURL",
            label="Site do servidor",
            section="Servidor",
            advanced=True,
        ),
        # --------------------------------------------------------------- Mundo
        ConfigField(
            key="GameWorld",
            label="Mundo",
            type=_ENUM,
            options=[
                "RWG",
                "Navezgane",
                "Pregen06k01",
                "Pregen06k02",
                "Pregen08k01",
                "Pregen08k02",
                "Pregen10k01",
            ],
            default="Navezgane",
            section="Mundo",
            description="RWG gera um mundo novo a partir da semente; os demais já vêm prontos.",
        ),
        ConfigField(
            key="WorldGenSeed",
            label="Semente do mundo",
            default="aether",
            section="Mundo",
            depends_on=_SO_RWG,
            description="Mesma semente e mesmo tamanho geram sempre o mesmo mundo.",
        ),
        ConfigField(
            key="WorldGenSize",
            label="Tamanho do mundo",
            type=_ENUM,
            options=["4096", "6144", "8192", "10240"],
            default="6144",
            section="Mundo",
            depends_on=_SO_RWG,
            description=(
                "Múltiplos de 2048. A partir da 3.0 o jogo só dá suporte oficial de "
                "6144 para cima; 4096 continua aí para servidores em versões antigas. "
                "Mundo maior demora bem mais para gerar e ocupa mais disco."
            ),
        ),
        ConfigField(
            key="GameName",
            label="Nome do save",
            default="World1",
            section="Mundo",
            description="Pasta onde o progresso é gravado. Trocar começa um jogo novo.",
        ),
        # ----------------------------------------------------------- Jogabilidade
        #
        # Dificuldade e ciclo dia/noite convivem em duas formas porque o jogo
        # mudou de ideia: até a 2.x eram propriedades próprias; da 3.0 em
        # diante viraram um código único de sandbox. As três ficam declaradas
        # e `fields_from_file` mostra só as que a versão instalada tem — é o
        # que faz o mesmo painel servir um servidor 3.0 e um alpha21.
        ConfigField(
            key="SandboxCode",
            label="Código de dificuldade (sandbox)",
            section="Jogabilidade",
            description=(
                "Desde a 3.0 a dificuldade e as regras do jogo vêm num código único. "
                "Gere o seu no jogo: novo jogo → opções de sandbox → copiar código."
            ),
        ),
        ConfigField(
            key="GameDifficulty",
            label="Dificuldade",
            type=_ENUM,
            options=["0", "1", "2", "3", "4", "5"],
            default="2",
            section="Jogabilidade",
            description=(
                "0 = mais fácil, 5 = insano. Versões 3.0+ não usam esta opção — "
                "nelas a dificuldade vem no código de sandbox."
            ),
        ),
        ConfigField(
            key="DayNightLength",
            label="Minutos por dia de jogo",
            type=_INT,
            default="60",
            minimum=10,
            maximum=120,
            section="Jogabilidade",
            description="Versões 3.0+ trazem esta opção dentro do código de sandbox.",
        ),
        ConfigField(
            key="PlayerKillingMode",
            label="Combate entre jogadores",
            type=_ENUM,
            options=["0", "1", "2", "3"],
            default="3",
            section="Jogabilidade",
            description="0 = ninguém, 1 = só aliados, 2 = só estranhos, 3 = todos.",
        ),
        ConfigField(
            key="BedrollExpiryTime",
            label="Validade do saco de dormir (dias reais)",
            type=_INT,
            default="45",
            minimum=0,
            section="Jogabilidade",
            advanced=True,
            description="Dias sem o dono entrar até a área deixar de ser protegida.",
        ),
        ConfigField(
            key="BuildCreate",
            label="Modo criativo",
            type=_BOOL,
            default="false",
            section="Jogabilidade",
            advanced=True,
        ),
        ConfigField(
            key="MaxSpawnedZombies",
            label="Máximo de zumbis no mundo",
            type=_INT,
            default="64",
            minimum=8,
            section="Jogabilidade",
            advanced=True,
            description="Mexer aqui tem impacto grande no desempenho do servidor.",
        ),
        # ------------------------------------------------------- Terreno reivindicado
        ConfigField(
            key="LandClaimCount",
            label="Reivindicações por jogador",
            type=_INT,
            default="5",
            minimum=1,
            section="Terreno reivindicado",
            advanced=True,
        ),
        ConfigField(
            key="LandClaimSize",
            label="Tamanho da reivindicação (blocos)",
            type=_INT,
            default="41",
            minimum=1,
            section="Terreno reivindicado",
            advanced=True,
        ),
        # ------------------------------------------------------------- Técnico
        ConfigField(
            key="ServerAllowCrossplay",
            label="Permitir crossplay",
            type=_BOOL,
            default="false",
            section="Técnico",
            advanced=True,
        ),
        ConfigField(
            key="EACEnabled",
            label="EasyAntiCheat",
            type=_BOOL,
            default="true",
            section="Técnico",
            advanced=True,
            description="Precisa ficar desligado para mods que trocam DLLs.",
        ),
        ConfigField(
            key="TelnetEnabled",
            label="Telnet",
            type=_BOOL,
            default="false",
            section="Técnico",
            advanced=True,
            description="O painel já dá console e comandos; ligue só se algo externo precisar.",
        ),
        ConfigField(
            key="TelnetPassword",
            label="Senha do telnet",
            type=_PWD,
            section="Técnico",
            advanced=True,
            description="Sem senha, o telnet só aceita conexões locais.",
        ),
        ConfigField(
            key="MaxChunkAge",
            label="Reset de área não visitada (dias de jogo)",
            type=_INT,
            default="-1",
            section="Técnico",
            advanced=True,
            description="-1 desliga. Áreas sem visita voltam ao original e liberam disco.",
        ),
        ConfigField(
            key="SaveDataLimit",
            label="Limite do save (MB)",
            type=_INT,
            default="-1",
            section="Técnico",
            advanced=True,
            description="-1 = sem limite. Ao estourar, o jogo reseta áreas para liberar espaço.",
        ),
    ],
)


def seed(root_dir: Path, valores: dict[str, str]) -> tuple[bool, list[str]]:
    """Prepara o serverconfig.xml da instância a partir do que o jogo instalou.

    Primeira instalação: copia o arquivo distribuído (com as ~69 propriedades
    e a documentação) e aplica em cima o que o usuário escolheu. Atualização:
    mantém o arquivo do usuário e só acrescenta o que a versão nova trouxe.

    Devolve ``(criou_agora, propriedades_novas)``.
    """
    distribuido = root_dir / CONFIG_DISTRIBUIDO
    destino = root_dir / CONFIG_FILE
    if not distribuido.is_file():
        return False, []

    texto_jogo = distribuido.read_text(encoding="utf-8", errors="replace")
    criou = not destino.is_file()
    novas: list[str] = []

    if criou:
        texto = texto_jogo
        codec = ServerConfigXmlCodec()
        conhecidas = {f.key for f in SERVERCONFIG_SCHEMA.fields}
        texto = codec.apply(texto, {k: v for k, v in valores.items() if k in conhecidas})
    else:
        texto = destino.read_text(encoding="utf-8", errors="replace")
        texto, novas = mesclar_novas(texto, texto_jogo)

    # Fixos do ambiente, não do usuário: sem eles os saves caem fora do volume
    # e a porta interna deixa de bater com o mapeamento do container.
    texto = garantir(texto, "UserDataFolder", "/data/UserData")
    texto = garantir(texto, "ServerPort", "26900")

    destino.write_text(texto, encoding="utf-8")
    return criou, novas


def config_warnings(root: Path, values: dict) -> list:
    return []
