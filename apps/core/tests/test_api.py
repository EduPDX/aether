"""API tests for the v1 skeleton."""

from aether_core import __version__
from aether_core.interfaces.http import create_app
from fastapi.testclient import TestClient


def client() -> TestClient:
    return TestClient(create_app())


def test_health():
    res = client().get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": __version__}


def test_providers_lists_minecraft():
    res = client().get("/api/v1/providers")
    assert res.status_code == 200
    providers = {p["manifest"]["id"]: p for p in res.json()}
    assert "minecraft" in providers
    ctype_ids = [ct["id"] for ct in providers["minecraft"]["contentTypes"]]
    assert "mod" in ctype_ids


def test_openapi_schema_is_served():
    res = client().get("/api/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "Aether Core"
