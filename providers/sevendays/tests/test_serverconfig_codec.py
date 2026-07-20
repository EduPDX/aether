"""Codec do serverconfig.xml: parse, apply e preservação do arquivo."""

from aether_provider_sevendays.server.serverconfig import (
    ServerConfigXmlCodec,
    render_initial_config,
)

EXEMPLO = """<?xml version="1.0"?>
<ServerSettings>
\t<!-- nome que aparece na lista -->
\t<property name="ServerName" value="Meu Servidor"/>
\t<property name="ServerMaxPlayerCount" value="8"/>
</ServerSettings>
"""


def test_parse_le_propriedades():
    values = ServerConfigXmlCodec().parse(EXEMPLO)
    assert values["ServerName"] == "Meu Servidor"
    assert values["ServerMaxPlayerCount"] == "8"


def test_apply_troca_valor_preservando_comentario():
    novo = ServerConfigXmlCodec().apply(EXEMPLO, {"ServerName": "Outro Nome"})
    assert '<property name="ServerName" value="Outro Nome"/>' in novo
    # O comentário e a outra propriedade continuam intactos.
    assert "<!-- nome que aparece na lista -->" in novo
    assert '<property name="ServerMaxPlayerCount" value="8"/>' in novo


def test_apply_insere_propriedade_ausente():
    """O jogo aceita propriedade em qualquer posição; ausente = adicionar,
    nunca falhar — é como um campo novo do schema chega a arquivos antigos."""
    novo = ServerConfigXmlCodec().apply(EXEMPLO, {"GameDifficulty": "3"})
    assert '<property name="GameDifficulty" value="3"/>' in novo
    assert novo.index("GameDifficulty") < novo.index("</ServerSettings>")


def test_apply_escapa_aspas():
    novo = ServerConfigXmlCodec().apply(EXEMPLO, {"ServerName": 'A "Base"'})
    assert 'value="A &quot;Base&quot;"' in novo
    assert ServerConfigXmlCodec().parse(novo)["ServerName"] == 'A "Base"'


def test_config_inicial_fixa_porta_e_userdata():
    """Porta interna e UserDataFolder não são escolha do usuário: a porta o
    mapeamento do container resolve, e saves fora do volume morrem com ele."""
    texto = render_initial_config({"ServerName": "Novo"})
    values = ServerConfigXmlCodec().parse(texto)
    assert values["ServerPort"] == "26900"
    assert values["UserDataFolder"] == "/data/UserData"
    assert values["ServerName"] == "Novo"
