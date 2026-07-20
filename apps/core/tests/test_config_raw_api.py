"""Modo avançado: editar o serverconfig.xml direto, com rede de segurança.

Editar o arquivo cru permite impedir o servidor de subir, então cada garantia
aqui (validar, guardar a versão anterior, restaurar) existe para tornar o erro
reversível.
"""

from pathlib import Path

XML_VALIDO = """<?xml version="1.0"?>
<ServerSettings>
\t<property name="ServerName" value="Servidor"/>
\t<property name="LandClaimCount" value="5"/>
</ServerSettings>
"""


def instancia_7dtd(client, tmp_path: Path) -> str:
    (tmp_path / "serverconfig.xml").write_text(XML_VALIDO, encoding="utf-8")
    res = client.post(
        "/api/v1/instances",
        json={
            "name": "7DTD",
            "provider_id": "sevendays",
            "root_dir": str(tmp_path),
            "runtime": "docker",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_le_o_arquivo_inteiro_inclusive_o_que_o_painel_nao_mapeia(client, tmp_path):
    iid = instancia_7dtd(client, tmp_path)
    body = client.get(f"/api/v1/instances/{iid}/config/raw?schema_id=serverconfig").json()

    assert body["format"] == "xml"
    assert "LandClaimCount" in body["content"]
    assert body["has_previous"] is False


def test_xml_invalido_e_recusado_com_linha_e_coluna(client, tmp_path):
    """Sem a posição, achar o erro num arquivo de 100 linhas vira caça ao
    tesouro — e o usuário está justamente com o servidor fora do ar."""
    iid = instancia_7dtd(client, tmp_path)
    res = client.post(
        f"/api/v1/instances/{iid}/config/raw/validate",
        json={
            "schema_id": "serverconfig",
            "content": "<ServerSettings><property></ServerSettings>",
        },
    )
    body = res.json()

    assert body["valid"] is False
    assert body["line"] >= 1
    assert body["column"] >= 1
    assert body["message"]


def test_validacao_aceita_xml_bem_formado(client, tmp_path):
    iid = instancia_7dtd(client, tmp_path)
    res = client.post(
        f"/api/v1/instances/{iid}/config/raw/validate",
        json={"schema_id": "serverconfig", "content": XML_VALIDO},
    )
    assert res.json() == {"valid": True}


def test_gravar_xml_quebrado_nao_toca_no_arquivo(client, tmp_path):
    """A validação acontece antes da escrita: um XML quebrado nunca chega ao
    disco, então o servidor continua conseguindo subir."""
    iid = instancia_7dtd(client, tmp_path)
    res = client.put(
        f"/api/v1/instances/{iid}/config/raw",
        json={"schema_id": "serverconfig", "content": "<ServerSettings>"},
    )

    assert res.status_code == 400
    assert "linha" in res.json()["detail"]
    assert (tmp_path / "serverconfig.xml").read_text() == XML_VALIDO


def test_gravar_guarda_a_versao_anterior_e_restaura(client, tmp_path):
    iid = instancia_7dtd(client, tmp_path)
    novo = XML_VALIDO.replace('value="Servidor"', 'value="Trocado"')

    res = client.put(
        f"/api/v1/instances/{iid}/config/raw",
        json={"schema_id": "serverconfig", "content": novo},
    )
    assert res.status_code == 200
    assert "Trocado" in (tmp_path / "serverconfig.xml").read_text()
    assert (tmp_path / "serverconfig.xml.anterior").is_file()

    restaurado = client.post(f"/api/v1/instances/{iid}/config/raw/restore?schema_id=serverconfig")
    assert restaurado.status_code == 200
    assert "Servidor" in (tmp_path / "serverconfig.xml").read_text()


def test_restaurar_sem_versao_anterior_avisa(client, tmp_path):
    iid = instancia_7dtd(client, tmp_path)
    res = client.post(f"/api/v1/instances/{iid}/config/raw/restore?schema_id=serverconfig")
    assert res.status_code == 404


def test_formulario_esconde_campo_que_a_versao_instalada_nao_tem(client, tmp_path):
    """O arquivo de teste só tem ServerName e LandClaimCount: nenhum outro
    campo do schema pode aparecer no formulário."""
    iid = instancia_7dtd(client, tmp_path)
    configs = client.get(f"/api/v1/instances/{iid}/config").json()
    chaves = {f["key"] for f in configs[0]["schema"]["fields"]}

    assert "ServerName" in chaves
    assert "GameWorld" not in chaves
    assert "SandboxCode" not in chaves


def test_salvar_opcao_inexistente_na_versao_e_recusado(client, tmp_path):
    """Antes isto inseria a propriedade no fim do arquivo e o jogo a ignorava
    em silêncio — o usuário achava que tinha configurado."""
    iid = instancia_7dtd(client, tmp_path)
    res = client.put(
        f"/api/v1/instances/{iid}/config",
        json={"schema_id": "serverconfig", "values": {"GameDifficulty": "4"}},
    )

    assert res.status_code == 400
    assert "não existem na versão instalada" in res.json()["detail"]
    assert "GameDifficulty" not in (tmp_path / "serverconfig.xml").read_text()
