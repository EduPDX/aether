import pytest
from fastapi.testclient import TestClient
from test_sync_api import create_and_publish, make_synced_instance


def test_invite_requires_published_profile_and_config(client, tmp_path, monkeypatch):
    iid, _ = make_synced_instance(client, tmp_path)
    pid = create_and_publish(client, iid)
    anon = TestClient(client.app)
    route = f"/api/v1/public/launcher/{pid}"
    assert anon.get(route).status_code == 404

    async def catalog_list():
        return [
            {
                "provider_id": "minecraft",
                "banner_url": "/api/v1/catalog/minecraft/media/banner.png",
                "atribuicao_da_imagem": "Autor · CC BY",
            }
        ]

    monkeypatch.setattr(client.app.state.catalog, "list", catalog_list)
    config = {
        "public_url": "https://aether.test/panel/",
        "game_address": "mc.test:25565",
        "map_url": "https://map.test",
    }
    assert client.put(f"/api/v1/instances/{iid}/launcher", json=config).status_code == 200
    data = anon.get(route).json()
    assert data["server"] == "https://aether.test/panel"
    assert data["profile_id"] == pid
    assert data["instance_id"] == iid
    assert data["game_address"] == "mc.test:25565"
    assert data["map_url"] == "https://map.test"
    assert "root_dir" not in data and "provider_data" not in data
    assert data["cover_url"].startswith("https://aether.test/panel/api/v1/catalog/")
    assert data["cover_credit"]
    config.update(
        map_url="https://new-map.test", cover_url="https://images.test/custom.png", name="Novo nome"
    )
    assert client.put(f"/api/v1/instances/{iid}/launcher", json=config).status_code == 200
    refreshed = anon.get(route).json()
    assert refreshed["map_url"] == "https://new-map.test"
    assert refreshed["cover_url"] == config["cover_url"]
    assert refreshed["name"] == "Novo nome"
    assert refreshed["cover_credit"] == ""
    client.delete(f"/api/v1/instances/{iid}/sync-profiles/{pid}")
    assert anon.get(route).status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("public_url", "javascript:alert(1)"),
        ("map_url", "file:///secret"),
        ("cover_url", "https://user:password@images.test/x.png"),
        ("public_url", "https://aether.test/?token=secret"),
        ("game_address", "mc.test:99999"),
        ("game_address", "mc.test --option"),
    ],
)
def test_rejects_unsafe_addresses(client, tmp_path, field, value):
    iid, _ = make_synced_instance(client, tmp_path)
    assert client.put(f"/api/v1/instances/{iid}/launcher", json={field: value}).status_code == 422


def test_launcher_settings_require_permissions(client, tmp_path):
    iid, _ = make_synced_instance(client, tmp_path)
    route = f"/api/v1/instances/{iid}/launcher"
    anon = TestClient(client.app)
    assert anon.get(route).status_code == 401
    assert anon.put(route, json={}).status_code == 401
    client.post(
        "/api/v1/users",
        json={"username": "invite_mod", "password": "password-12345", "role": "moderator"},
    )
    login = anon.post(
        "/api/v1/auth/login", json={"username": "invite_mod", "password": "password-12345"}
    ).json()
    anon.headers["Authorization"] = f"Bearer {login['access_token']}"
    assert anon.get(route).status_code == 403
    assert anon.put(route, json={}).status_code == 403


def test_unpublished_profile_is_not_invitable(client, tmp_path):
    iid, _ = make_synced_instance(client, tmp_path)
    client.put(f"/api/v1/instances/{iid}/launcher", json={"public_url": "https://aether.test"})
    pid = client.post(
        f"/api/v1/instances/{iid}/sync-profiles",
        json={
            "name": "Draft",
            "rules": {"rules": [{"dir": "mods", "patterns": ["*.jar"], "action": "require"}]},
        },
    ).json()["id"]
    assert client.get(f"/api/v1/public/launcher/{pid}").status_code == 404
