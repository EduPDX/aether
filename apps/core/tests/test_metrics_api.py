"""Metrics API and client-profile content type."""

from conftest import create_instance


def test_metrics_reports_host_resources(client, tmp_path):
    create_instance(client, tmp_path / "srv" if (tmp_path / "srv").mkdir() is None else tmp_path)
    res = client.get("/api/v1/metrics")
    assert res.status_code == 200
    body = res.json()

    host = body["host"]
    assert host["cpu_count"] >= 1
    assert host["mem_total"] > 0
    assert 0 <= host["mem_percent"] <= 100
    assert host["disk_total"] > 0
    assert host["uptime_seconds"] > 0

    # instância parada aparece com processo inativo
    assert body["instances"], "deve listar as instâncias"
    assert body["instances"][0]["running"] is False
    # o histórico ganha um ponto a cada leitura
    assert len(body["history"]) >= 1


def test_client_mods_are_a_separate_content_type(client, tmp_path):
    root = tmp_path / "srv2"
    (root / "mods").mkdir(parents=True)
    (root / "mods" / "servidor.jar").write_bytes(b"s")
    # sem override: usa os diretórios padrão do provider (mods/ e
    # aether-client/mods/), que é como o usuário cria pela interface
    res = client.post(
        "/api/v1/instances",
        json={"name": "Com cliente", "provider_id": "minecraft", "root_dir": str(root)},
    )
    assert res.status_code == 201, res.text
    iid = res.json()["id"]

    # o tipo existe no provider
    providers = client.get("/api/v1/providers").json()
    ctypes = {c["id"]: c for c in providers[0]["content_types"]}
    assert ctypes["mod_client"]["default_directory"] == "aether-client/mods"

    # a pasta do perfil de cliente é criada sob demanda e começa vazia
    res = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod_client"})
    assert res.status_code == 200
    assert res.json() == []
    assert (root / "aether-client" / "mods").is_dir()

    # enviar um mod de cliente não mexe nos mods do servidor
    up = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "aether-client/mods"},
        files=[("uploads", ("Jade.jar", b"cliente", "application/java-archive"))],
    )
    assert up.status_code == 200
    client_mods = client.get(
        f"/api/v1/instances/{iid}/content", params={"type": "mod_client"}
    ).json()
    server_mods = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    assert [m["file"] for m in client_mods] == ["Jade.jar"]
    assert [m["file"] for m in server_mods] == ["servidor.jar"]
