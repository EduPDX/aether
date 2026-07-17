"""API tests for the v1 skeleton."""

from aether_core import __version__


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": __version__}


def test_providers_lists_minecraft(client):
    res = client.get("/api/v1/providers")
    assert res.status_code == 200
    providers = {p["manifest"]["id"]: p for p in res.json()}
    assert "minecraft" in providers
    ctypes = {ct["id"]: ct for ct in providers["minecraft"]["content_types"]}
    assert ctypes["mod"]["default_directory"] == "mods"


def test_openapi_schema_is_served(client):
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "Aether Core"
