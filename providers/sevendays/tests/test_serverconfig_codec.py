"""Codec do serverconfig.xml, exercitado contra o arquivo real da versão 3.0.1.

A fixture é o arquivo que o jogo distribui, copiado do servidor de produção:
69 propriedades, cada uma documentada num comentário ao lado. Testar contra
ele (e não contra um XML inventado) é o que pega as armadilhas de formato.
"""

from pathlib import Path

from aether_provider_sevendays.server.serverconfig import (
    SERVERCONFIG_SCHEMA,
    ServerConfigXmlCodec,
    garantir,
    mesclar_novas,
    seed,
)

FIXTURES = Path(__file__).parent / "fixtures"
DISTRIBUIDO = (FIXTURES / "serverconfig-3.0.1.xml").read_text(encoding="utf-8")

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


def test_parse_ignora_propriedade_comentada():
    """O arquivo do jogo traz a UserDataFolder comentada como exemplo. Lê-la
    como ativa fazia o painel exibir 'absolute_path' como se valesse."""
    values = ServerConfigXmlCodec().parse(DISTRIBUIDO)
    assert "UserDataFolder" not in values
    assert len(values) == 68  # 69 no arquivo, uma delas comentada


def test_apply_troca_valor_preservando_comentario():
    novo = ServerConfigXmlCodec().apply(EXEMPLO, {"ServerName": "Outro Nome"})
    assert '<property name="ServerName" value="Outro Nome"/>' in novo
    assert "<!-- nome que aparece na lista -->" in novo
    assert '<property name="ServerMaxPlayerCount" value="8"/>' in novo


def test_apply_ignora_chave_que_nao_existe_no_arquivo():
    """A 3.0 removeu GameDifficulty. Inserir a propriedade de volta não
    configura nada — o jogo ignora — e ainda suja o arquivo dando a impressão
    de que a opção foi aplicada."""
    novo = ServerConfigXmlCodec().apply(DISTRIBUIDO, {"GameDifficulty": "4"})
    assert "GameDifficulty" not in novo
    assert novo == DISTRIBUIDO


def test_apply_preserva_documentacao_do_jogo():
    novo = ServerConfigXmlCodec().apply(DISTRIBUIDO, {"ServerName": "Aether"})
    assert 'value="Aether"' in novo
    assert "<!-- Whatever you want the name of the server to be. -->" in novo
    # Nada além do valor mudou: mesmo número de linhas e de propriedades.
    assert len(novo.splitlines()) == len(DISTRIBUIDO.splitlines())
    assert novo.count("<property") == DISTRIBUIDO.count("<property")


def test_apply_escapa_aspas():
    novo = ServerConfigXmlCodec().apply(EXEMPLO, {"ServerName": 'A "Base"'})
    assert 'value="A &quot;Base&quot;"' in novo
    assert ServerConfigXmlCodec().parse(novo)["ServerName"] == 'A "Base"'


def test_garantir_cria_propriedade_ausente():
    """Exceção consciente: UserDataFolder vem comentada no arquivo do jogo e
    precisa existir, ou os saves caem fora do volume do container."""
    novo = garantir(DISTRIBUIDO, "UserDataFolder", "/data/UserData")
    assert ServerConfigXmlCodec().parse(novo)["UserDataFolder"] == "/data/UserData"


def test_garantir_substitui_quando_ja_existe():
    novo = garantir(EXEMPLO, "ServerName", "Trocado")
    assert ServerConfigXmlCodec().parse(novo)["ServerName"] == "Trocado"
    assert novo.count("ServerName") == 1


def test_mesclar_traz_propriedades_novas_preservando_valores():
    """Ao atualizar o jogo, o arquivo do usuário precisa ganhar as opções que
    a versão nova trouxe — senão elas ficam inacessíveis pelo painel."""
    antigo = """<?xml version="1.0"?>
<ServerSettings>
\t<property name="ServerName" value="Escolhido pelo dono"/>
</ServerSettings>
"""
    novo, adicionadas = mesclar_novas(antigo, DISTRIBUIDO)
    valores = ServerConfigXmlCodec().parse(novo)

    assert valores["ServerName"] == "Escolhido pelo dono"  # valor do usuário intacto
    assert "SandboxCode" in adicionadas
    assert valores["SandboxCode"]  # veio com o padrão do jogo
    assert "UserDataFolder" not in adicionadas  # comentada no arquivo do jogo


def test_mesclar_sem_novidade_nao_mexe_no_arquivo():
    novo, adicionadas = mesclar_novas(DISTRIBUIDO, DISTRIBUIDO)
    assert adicionadas == []
    assert novo == DISTRIBUIDO


def test_seed_primeira_instalacao_parte_do_arquivo_do_jogo(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "serverconfig.xml").write_text(DISTRIBUIDO, encoding="utf-8")

    criou, novas = seed(tmp_path, {"ServerName": "Meu 7DTD", "GameWorld": "RWG"})
    valores = ServerConfigXmlCodec().parse((tmp_path / "serverconfig.xml").read_text())

    assert criou is True
    assert novas == []
    # As 68 propriedades ativas do jogo continuam lá — não só as que conhecemos.
    assert len(valores) >= 68
    assert valores["ServerName"] == "Meu 7DTD"
    assert valores["GameWorld"] == "RWG"
    # Fixos do ambiente aplicados por cima.
    assert valores["UserDataFolder"] == "/data/UserData"
    assert valores["ServerPort"] == "26900"


def test_seed_em_atualizacao_preserva_o_que_o_usuario_configurou(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "serverconfig.xml").write_text(DISTRIBUIDO, encoding="utf-8")
    (tmp_path / "serverconfig.xml").write_text(
        '<?xml version="1.0"?>\n<ServerSettings>\n'
        '\t<property name="ServerName" value="Servidor Antigo"/>\n'
        "</ServerSettings>\n",
        encoding="utf-8",
    )

    criou, novas = seed(tmp_path, {"ServerName": "ignorado numa atualização"})
    valores = ServerConfigXmlCodec().parse((tmp_path / "serverconfig.xml").read_text())

    assert criou is False
    assert valores["ServerName"] == "Servidor Antigo"
    assert "SandboxCode" in novas


def test_dificuldade_convive_nas_duas_formas_que_o_jogo_ja_teve():
    """Até a 2.x a dificuldade era GameDifficulty; da 3.0 em diante virou o
    código de sandbox. As duas ficam no schema e a versão instalada decide
    qual aparece — é o que faz o mesmo painel servir 3.0 e alpha21."""
    chaves = {f.key for f in SERVERCONFIG_SCHEMA.fields}
    assert {"GameDifficulty", "DayNightLength", "SandboxCode"} <= chaves


def test_na_3_0_o_formulario_esconde_o_que_a_versao_nao_tem():
    """fields_from_file é o que evita oferecer configuração que o jogo ignora:
    no arquivo da 3.0.1 não existe GameDifficulty, então o campo some."""
    assert SERVERCONFIG_SCHEMA.fields_from_file is True
    do_arquivo = set(ServerConfigXmlCodec().parse(DISTRIBUIDO))

    assert "GameDifficulty" not in do_arquivo
    assert "DayNightLength" not in do_arquivo
    assert "SandboxCode" in do_arquivo

    # E o que sobra do schema existe mesmo na 3.0.1 (fora os de outras versões
    # e a UserDataFolder, que vem comentada no arquivo do jogo).
    do_schema = {f.key for f in SERVERCONFIG_SCHEMA.fields}
    orfas = do_schema - do_arquivo - {"UserDataFolder"}
    assert orfas == {"GameDifficulty", "DayNightLength"}


def test_semente_e_tamanho_so_aparecem_em_mundo_gerado():
    por_chave = {f.key: f for f in SERVERCONFIG_SCHEMA.fields}
    assert por_chave["WorldGenSeed"].depends_on == {"GameWorld": "RWG"}
    assert por_chave["WorldGenSize"].depends_on == {"GameWorld": "RWG"}
