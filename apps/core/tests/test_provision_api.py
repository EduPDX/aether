"""Criação de instância do zero (runtime docker + provision) pela API.

Nada aqui precisa de Docker: o provision só escreve arquivos; o container
entraria em cena na primeira inicialização.
"""

from pathlib import Path


def test_criar_instancia_minecraft_do_zero(client):
    res = client.post(
        "/api/v1/instances",
        json={
            "name": "MC Container",
            "provider_id": "minecraft",
            "runtime": "docker",
            "provision_values": {"eula": "true", "type": "FORGE", "version": "1.20.1"},
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["runtime"] == "docker"
    # O Core criou e é dono do root_dir — o usuário não apontou pasta nenhuma.
    assert Path(body["root_dir"]).is_dir()
    assert body["provider_data"]["container"]["type"] == "FORGE"


def test_eula_recusada_barra_a_criacao(client):
    res = client.post(
        "/api/v1/instances",
        json={
            "name": "Sem EULA",
            "provider_id": "minecraft",
            "runtime": "docker",
            "provision_values": {"eula": "false"},
        },
    )
    assert res.status_code == 400
    assert "EULA" in res.json()["detail"]


def test_criar_instancia_sevendays_guarda_escolhas_para_apos_instalar(client):
    """O serverconfig.xml precisa ser cópia do arquivo da versão instalada, e
    na criação o jogo ainda não existe em disco. As respostas ficam pendentes
    até o after_install — nunca geramos o arquivo do zero."""
    res = client.post(
        "/api/v1/instances",
        json={
            "name": "7DTD",
            "provider_id": "sevendays",
            "runtime": "docker",
            "provision_values": {"ServerName": "Meu 7DTD"},
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    root = Path(body["root_dir"])

    assert not (root / "serverconfig.xml").exists()
    assert body["provider_data"]["pending_config"]["ServerName"] == "Meu 7DTD"
    assert (root / "UserData").is_dir()


def test_runtime_desconhecido_e_recusado(client, tmp_path):
    res = client.post(
        "/api/v1/instances",
        json={
            "name": "X",
            "provider_id": "minecraft",
            "root_dir": str(tmp_path),
            "runtime": "kubernetes",
        },
    )
    assert res.status_code == 400


def test_providers_expoem_capabilities_e_schema(client):
    body = client.get("/api/v1/providers").json()
    por_id = {p["manifest"]["id"]: p for p in body}

    mc = por_id["minecraft"]
    assert mc["capabilities"]["launch"] is True
    assert mc["capabilities"]["container"] is True
    assert mc["capabilities"]["provision"] is True
    assert any(f["key"] == "eula" for f in mc["provision_schema"]["fields"])
    assert mc["manifest"]["icon_spec"] == {"file": "server-icon.png", "size": 64}

    sd = por_id["sevendays"]
    # 7DTD só roda containerizado: launch é False e a UI não oferece processo.
    assert sd["capabilities"]["launch"] is False
    assert sd["capabilities"]["container"] is True
    assert sd["manifest"]["icon_spec"] is None
