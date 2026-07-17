"""Authentication, RBAC and audit tests."""

from conftest import OWNER, authenticate
from fastapi.testclient import TestClient


def test_setup_flow(anon_client: TestClient):
    assert anon_client.get("/api/v1/auth/status").json() == {"setup_required": True}

    res = anon_client.post("/api/v1/auth/setup", json=OWNER)
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["role"] == "owner"
    assert body["access_token"] and body["refresh_token"]

    assert anon_client.get("/api/v1/auth/status").json() == {"setup_required": False}
    # segundo setup é bloqueado
    assert anon_client.post("/api/v1/auth/setup", json=OWNER).status_code == 409


def test_login_and_me(anon_client: TestClient):
    anon_client.post("/api/v1/auth/setup", json=OWNER)

    wrong = anon_client.post(
        "/api/v1/auth/login", json={"username": OWNER["username"], "password": "errada-12345"}
    )
    assert wrong.status_code == 401

    body = authenticate(anon_client)
    me = anon_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == OWNER["username"]

    refreshed = anon_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


def test_endpoints_require_auth(anon_client: TestClient):
    anon_client.post("/api/v1/auth/setup", json=OWNER)
    assert anon_client.get("/api/v1/instances").status_code == 401
    assert anon_client.get("/api/v1/providers").status_code == 401
    assert anon_client.get("/api/v1/health").status_code == 200  # público


def test_invalid_token_rejected(anon_client: TestClient):
    anon_client.post("/api/v1/auth/setup", json=OWNER)
    anon_client.headers["Authorization"] = "Bearer nao-e-um-token"
    assert anon_client.get("/api/v1/instances").status_code == 401


def test_rbac_viewer_cannot_write(client: TestClient, tmp_path):
    res = client.post(
        "/api/v1/users",
        json={"username": "espectador", "password": "senha-viewer-1", "role": "viewer"},
    )
    assert res.status_code == 201

    viewer = TestClient(client.app)
    login = viewer.post(
        "/api/v1/auth/login", json={"username": "espectador", "password": "senha-viewer-1"}
    ).json()
    viewer.headers["Authorization"] = f"Bearer {login['access_token']}"

    # leitura ok
    assert viewer.get("/api/v1/instances").status_code == 200
    # escrita negada
    mods = tmp_path / "m"
    mods.mkdir()
    res = viewer.post(
        "/api/v1/instances",
        json={"name": "X", "provider_id": "minecraft", "root_dir": str(mods)},
    )
    assert res.status_code == 403
    # gestão de usuários negada
    assert viewer.get("/api/v1/users").status_code == 403


def test_user_management_rules(client: TestClient):
    # não pode criar outro owner
    res = client.post(
        "/api/v1/users",
        json={"username": "usurpador", "password": "senha-owner-12", "role": "owner"},
    )
    assert res.status_code == 400

    # não pode se auto-deletar
    me = client.get("/api/v1/auth/me").json()
    assert client.delete(f"/api/v1/users/{me['id']}").status_code == 400

    # cria e deleta um moderador
    created = client.post(
        "/api/v1/users",
        json={"username": "mod1", "password": "senha-mod-123", "role": "moderator"},
    ).json()
    assert client.delete(f"/api/v1/users/{created['id']}").status_code == 204


def test_audit_log_records_actions(client: TestClient, tmp_path):
    mods = tmp_path / "m"
    mods.mkdir()
    client.post(
        "/api/v1/instances",
        json={"name": "Audit", "provider_id": "minecraft", "root_dir": str(mods)},
    )
    entries = client.get("/api/v1/audit").json()
    actions = [e["action"] for e in entries]
    assert any("POST /api/v1/instances" in a for a in actions)
    assert any(a.startswith("auth.") for a in actions)
    assert all("password" not in a.lower() for a in actions)
