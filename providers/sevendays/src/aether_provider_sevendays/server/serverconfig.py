"""serverconfig.xml: schema de configuração e codec XML.

O formato do jogo é uma lista chata de ``<property name="..." value="..."/>``
dentro de ``<ServerSettings>``. O codec trabalha por regex linha a linha em
vez de reescrever o documento: é o que preserva comentários e a ordem que o
usuário (ou um guia da comunidade) deixou no arquivo.
"""

import re
from pathlib import Path
from xml.sax.saxutils import escape, unescape

from aether_sdk import ConfigField, ConfigFieldType, ConfigSchema

CONFIG_FILE = "serverconfig.xml"

_PROP = re.compile(r'<property\s+name="([^"]+)"\s+value="([^"]*)"\s*/>')
_FECHO = re.compile(r"</ServerSettings>")

SERVERCONFIG_SCHEMA = ConfigSchema(
    id="serverconfig",
    label="serverconfig.xml",
    file=CONFIG_FILE,
    format="xml",
    fields=[
        ConfigField(key="ServerName", label="Nome do servidor", default="Aether Server"),
        ConfigField(
            key="ServerPassword",
            label="Senha",
            type=ConfigFieldType.PASSWORD,
            description="Vazio = servidor aberto.",
        ),
        ConfigField(
            key="ServerMaxPlayerCount",
            label="Máximo de jogadores",
            type=ConfigFieldType.INTEGER,
            default="8",
            minimum=1,
            maximum=64,
        ),
        ConfigField(
            key="GameWorld",
            label="Mundo",
            type=ConfigFieldType.ENUM,
            options=["Navezgane", "RWG"],
            default="Navezgane",
            description="RWG gera um mundo aleatório a partir da seed.",
        ),
        ConfigField(key="WorldGenSeed", label="Seed (RWG)", default="aether"),
        ConfigField(
            key="GameDifficulty",
            label="Dificuldade",
            type=ConfigFieldType.INTEGER,
            default="1",
            minimum=0,
            maximum=5,
            description="0 = mais fácil, 5 = insano.",
        ),
        ConfigField(key="GameName", label="Nome do save", default="World1", advanced=True),
        ConfigField(key="ServerDescription", label="Descrição", default="", advanced=True),
        ConfigField(
            key="ServerVisibility",
            label="Visibilidade",
            type=ConfigFieldType.INTEGER,
            default="2",
            minimum=0,
            maximum=2,
            description="2 = pública, 1 = só amigos, 0 = fora da lista.",
            advanced=True,
        ),
        ConfigField(
            key="WorldGenSize",
            label="Tamanho do mundo (RWG)",
            type=ConfigFieldType.INTEGER,
            default="6144",
            minimum=2048,
            maximum=16384,
            advanced=True,
        ),
        ConfigField(
            key="DayNightLength",
            label="Minutos por dia de jogo",
            type=ConfigFieldType.INTEGER,
            default="60",
            minimum=10,
            maximum=120,
            advanced=True,
        ),
        ConfigField(
            key="EACEnabled",
            label="EasyAntiCheat",
            type=ConfigFieldType.BOOLEAN,
            default="true",
            description="Precisa estar desligado para servidores com mods de DLL.",
            advanced=True,
        ),
        ConfigField(
            key="TelnetEnabled",
            label="Telnet",
            type=ConfigFieldType.BOOLEAN,
            default="false",
            advanced=True,
        ),
    ],
)


class ServerConfigXmlCodec:
    """Lê e altera propriedades preservando o resto do arquivo."""

    def parse(self, text: str) -> dict[str, str]:
        # &quot; entra na tabela extra: o sax só desfaz &amp;/&lt;/&gt; por padrão.
        return {name: unescape(value, {"&quot;": '"'}) for name, value in _PROP.findall(text)}

    def apply(self, text: str, values: dict[str, str]) -> str:
        for key, value in values.items():
            seguro = escape(str(value), {'"': "&quot;"})
            padrao = re.compile(
                r'(<property\s+name="' + re.escape(key) + r'"\s+value=")[^"]*("\s*/>)'
            )
            novo, trocas = padrao.subn(rf"\g<1>{seguro}\g<2>", text)
            if trocas:
                text = novo
            else:
                # Propriedade ausente entra antes do fecho — o jogo aceita
                # qualquer ordem, e assim não tocamos no que já existe.
                text = _FECHO.sub(
                    f'\t<property name="{key}" value="{seguro}"/>\n</ServerSettings>',
                    text,
                    count=1,
                )
        return text


def render_initial_config(values: dict[str, str]) -> str:
    """Gera o serverconfig.xml de uma instância nova.

    ``ServerPort`` e ``UserDataFolder`` não são escolhas do usuário: a porta
    interna do container é fixa (o mapeamento decide a externa) e os saves
    precisam morar no volume — fora dele, morrem com o container.
    """
    fixos = {
        "ServerPort": "26900",
        "UserDataFolder": "/data/UserData",
        "WebDashboardEnabled": "false",
    }
    linhas = ['<?xml version="1.0"?>', "<ServerSettings>"]
    vistos: dict[str, str] = {}
    for f in SERVERCONFIG_SCHEMA.fields:
        vistos[f.key] = str(values.get(f.key, f.default))
    vistos.update(fixos)
    for chave, valor in vistos.items():
        linhas.append(f'\t<property name="{chave}" value="{escape(valor, {chr(34): "&quot;"})}"/>')
    linhas.append("</ServerSettings>")
    return "\n".join(linhas) + "\n"


def config_warnings(root: Path, values: dict) -> list:
    return []
