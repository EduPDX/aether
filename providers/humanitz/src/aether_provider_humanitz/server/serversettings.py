"""GameServerSettings.ini: schema de configuração e codec INI.

O HumanitZ segue o mesmo princípio do 7 Days to Die: a base é sempre o arquivo
que o **jogo distribui** (``REF_GameServerSettings.ini``, que o SteamCMD
atualiza a cada versão), nunca um arquivo gerado por nós. Assim o painel só
mexe nas chaves que conhece e preserva o resto — inclusive as dezenas de opções
de mundo que ele não mapeia e os comentários que documentam cada uma.

Daí as regras deste módulo:

- ``apply`` só troca o valor de chave que já existe; nunca inventa;
- o formato preserva comentários (``;``), seções (``[...]``), ordem e o estilo
  de aspas de cada valor;
- o que o painel não mapeia fica intocado — quem precisa mexer usa o editor
  bruto da interface.
"""

import re
from pathlib import Path

from aether_sdk import (
    ConfigField,
    ConfigFieldType,
    ConfigSchema,
    ConfigWarning,
)

# Ativo = a linha do jogo distribui em REF_ e a primeira subida copia para cá.
CONFIG_FILE = "server/HumanitZServer/GameServerSettings.ini"
CONFIG_DISTRIBUIDO = "server/HumanitZServer/REF_GameServerSettings.ini"

# `Chave=Valor`, tolerando espaços; linhas de comentário (;) e seção ([...])
# não casam. O valor pode vir com ou sem aspas.
_LINHA = re.compile(
    r"^(?P<pre>\s*)(?P<key>[A-Za-z0-9_]+)(?P<mid>\s*=\s*)(?P<val>.*?)(?P<post>\s*)$"
)


def _e_comentario(linha: str) -> bool:
    despido = linha.lstrip()
    return despido.startswith(";") or despido.startswith("[")


def _desaspar(valor: str) -> str:
    if len(valor) >= 2 and valor[0] == '"' and valor[-1] == '"':
        return valor[1:-1]
    return valor


class GameServerIniCodec:
    """Lê e altera chaves preservando comentários, seções e formatação."""

    def parse(self, texto: str) -> dict[str, str]:
        valores: dict[str, str] = {}
        for linha in texto.splitlines():
            if _e_comentario(linha):
                continue
            m = _LINHA.match(linha)
            if m and m.group("key") not in valores:
                # Primeira ocorrência vence: a mesma chave não se repete entre
                # seções neste arquivo, mas se repetir o topo é o que vale.
                valores[m.group("key")] = _desaspar(m.group("val"))
        return valores

    def apply(self, texto: str, values: dict[str, str]) -> str:
        """Substitui o valor das chaves existentes, uma vez cada.

        Chave que não existe no arquivo é **ignorada**: escrever uma opção que a
        versão instalada não conhece só polui o arquivo e dá a falsa impressão
        de que a configuração pegou.
        """
        pendentes = dict(values)
        saida: list[str] = []
        for linha in texto.splitlines():
            m = None if _e_comentario(linha) else _LINHA.match(linha)
            if m and m.group("key") in pendentes:
                novo = pendentes.pop(m.group("key"))
                aspas = m.group("val").startswith('"')
                valor = f'"{novo}"' if aspas else novo
                linha = f"{m.group('pre')}{m.group('key')}{m.group('mid')}{valor}"
            saida.append(linha)
        fim = "\n" if texto.endswith("\n") else ""
        return "\n".join(saida) + fim


# --------------------------------------------------------------------- schema --
# Só as opções que valem a pena ter na tela. `fields_from_file=True` faz o Core
# esconder as que a versão instalada não trouxer, então declarar uma opção a
# mais que uma versão removeu não quebra nada.
SETTINGS_SCHEMA = ConfigSchema(
    id="humanitz-settings",
    label="Configuração do servidor HumanitZ",
    file=CONFIG_FILE,
    format="ini",
    fields_from_file=True,
    fields=[
        ConfigField(
            key="ServerName",
            label="Nome do servidor",
            description='Aparece no navegador de servidores. Evite a palavra "Official".',
        ),
        ConfigField(
            key="Password",
            label="Senha de entrada",
            type=ConfigFieldType.PASSWORD,
            description="Vazio = qualquer um pode entrar.",
        ),
        ConfigField(
            key="MaxPlayers",
            label="Máximo de jogadores",
            type=ConfigFieldType.INTEGER,
            default="16",
            minimum=1,
            maximum=64,
        ),
        ConfigField(
            key="SaveName",
            label="Nome do save",
            description="Troca o mundo em uso; útil para manter vários mundos.",
        ),
        ConfigField(
            key="AdminPass",
            label="Senha de admin",
            type=ConfigFieldType.PASSWORD,
            description="Usada com /adminaccess <senha> dentro do jogo.",
        ),
        ConfigField(
            key="PVP",
            label="PVP",
            type=ConfigFieldType.BOOLEAN,
            default="false",
            description="Combate entre jogadores.",
        ),
        ConfigField(
            key="PermaDeath",
            label="Morte permanente",
            type=ConfigFieldType.BOOLEAN,
            default="false",
            section="Mundo",
            advanced=True,
        ),
        ConfigField(
            key="XpMultiplier",
            label="Multiplicador de XP",
            default="1",
            section="Mundo",
            advanced=True,
        ),
        ConfigField(
            key="SaveIntervalSec",
            label="Intervalo de autosave (s)",
            type=ConfigFieldType.INTEGER,
            default="300",
            section="Mundo",
            advanced=True,
            description="0 desliga o autosave.",
        ),
        ConfigField(
            key="AirDrop",
            label="Airdrops",
            type=ConfigFieldType.BOOLEAN,
            default="true",
            section="Mundo",
            advanced=True,
        ),
        ConfigField(
            key="RCONEnabled",
            label="RCON",
            type=ConfigFieldType.BOOLEAN,
            default="false",
            section="Administração",
            advanced=True,
            description="Habilita RCON e mostra o ping no navegador de servidores.",
        ),
    ],
)


def seed(root: Path, pending: dict[str, str]) -> bool:
    """Prepara o GameServerSettings.ini a partir do arquivo do jogo.

    O jogo distribui ``REF_GameServerSettings.ini`` (o SteamCMD o atualiza a
    cada versão) e, na primeira subida, copia-o para ``GameServerSettings.ini``.
    Fazemos essa cópia aqui, logo após a instalação, para já aplicar as escolhas
    do usuário — do contrário o primeiro boot subiria com os padrões e só a
    segunda subida respeitaria a configuração.

    Devolve ``True`` quando criou o arquivo agora; ``False`` quando ele já
    existia (uma atualização não sobrescreve a config do usuário).
    """
    ativo = Path(root) / CONFIG_FILE
    referencia = Path(root) / CONFIG_DISTRIBUIDO
    criou = False
    if not ativo.is_file():
        if not referencia.is_file():
            return False
        ativo.parent.mkdir(parents=True, exist_ok=True)
        ativo.write_text(referencia.read_text(encoding="utf-8"), encoding="utf-8")
        criou = True
    if pending:
        texto = ativo.read_text(encoding="utf-8")
        ativo.write_text(GameServerIniCodec().apply(texto, pending), encoding="utf-8")
    return criou


def config_warnings(root, values: dict[str, str]) -> list[ConfigWarning]:
    avisos: list[ConfigWarning] = []
    nome = values.get("ServerName", "")
    if "official" in nome.lower():
        # O próprio arquivo do jogo avisa: nome com "Official" pode impedir o
        # servidor de subir ou de aparecer na lista.
        avisos.append(
            ConfigWarning(
                key="ServerName",
                message='Nomes com "Official" podem impedir o servidor de aparecer na lista.',
                level="error",
            )
        )
    return avisos
