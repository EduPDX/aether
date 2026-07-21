"""Troca de versão do Minecraft pela API (runtime docker, sem instalador).

Nada aqui precisa de Docker: trocar a versão só edita o provider_data; o
container entra em cena na próxima subida.
"""

import pytest

MANIFESTO = {
    "versions": [
        {"id": "1.21.1", "type": "release"},
        {"id": "1.20.1", "type": "release"},
        {"id": "24w33a", "type": "snapshot"},
    ]
}


@pytest.fixture(autouse=True)
def _sem_rede(client):
    """A lista de versões vem da Mojang; nos testes, injeta um manifesto fixo no
    provider em vez de ir à rede real (lento e frágil)."""
    provider = client.app.state.providers.get("minecraft")

    async def http_falso(_url, params=None):
        return MANIFESTO

    provider._http = http_falso
    provider._versoes_cache = None
    yield


def _criar(client, *, tipo="FORGE", versao="1.20.1"):
    res = client.post(
        "/api/v1/instances",
        json={
            "name": f"MC {tipo}",
            "provider_id": "minecraft",
            "runtime": "docker",
            "provision_values": {"eula": "true", "type": tipo, "version": versao},
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_estado_da_versao_forge(client):
    iid = _criar(client, tipo="FORGE", versao="1.20.1")
    dados = client.get(f"/api/v1/instances/{iid}/game-version").json()

    assert dados["current"] == "1.20.1"
    assert dados["modded"] is True  # Forge tem mods presos à versão
    assert dados["running"] is False
    ids = [v["id"] for v in dados["available"]]
    assert ids == ["1.21.1", "1.20.1", "24w33a"]


def test_vanilla_nao_e_modado(client):
    iid = _criar(client, tipo="VANILLA", versao="1.20.4")
    dados = client.get(f"/api/v1/instances/{iid}/game-version").json()
    assert dados["modded"] is False


def test_trocar_versao_atualiza_o_provider_data(client):
    iid = _criar(client, tipo="FORGE", versao="1.20.1")

    res = client.post(
        f"/api/v1/instances/{iid}/game-version",
        json={"version": "1.21.1", "skip_backup": True},
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"version": "1.21.1", "backed_up": False}

    # a versão fixada mudou, o resto do container não
    dados = client.get(f"/api/v1/instances/{iid}/game-version").json()
    assert dados["current"] == "1.21.1"
    inst = client.get(f"/api/v1/instances/{iid}").json()
    assert inst["provider_data"]["container"]["type"] == "FORGE"
    assert inst["provider_data"]["container"]["version"] == "1.21.1"


def test_trocar_recusa_versao_vazia(client):
    iid = _criar(client)
    res = client.post(
        f"/api/v1/instances/{iid}/game-version",
        json={"version": "", "skip_backup": True},
    )
    assert res.status_code == 422  # pydantic: min_length


def test_provider_sem_troca_de_versao_nao_expoe(client, tmp_path):
    """Uma instância de processo (pasta adotada) não tem bloco container, mas o
    provider Minecraft suporta a capacidade — o current só fica vazio."""
    root = tmp_path / "adotada"
    root.mkdir()
    (root / "server.properties").write_text("online-mode=false\n")
    res = client.post(
        "/api/v1/instances",
        json={"name": "Adotada", "provider_id": "minecraft", "root_dir": str(root)},
    )
    iid = res.json()["id"]
    dados = client.get(f"/api/v1/instances/{iid}/game-version").json()
    assert dados["current"] == ""  # sem container, sem versão fixada
    assert dados["modded"] is False
