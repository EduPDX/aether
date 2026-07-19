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


# ------------------------------------------------------ perfil e senha --


def _logar(client, usuario="admin", senha="senha-forte-123"):
    return client.post(
        "/api/v1/auth/login", json={"username": usuario, "password": senha}
    ).json()


def test_password_change_requires_the_current_one(client):
    """Sem exigir a atual, uma aba esquecida aberta viraria tomada de conta."""
    res = client.post(
        "/api/v1/auth/password",
        json={"current_password": "errada", "new_password": "outra-senha-123"},
    )
    assert res.status_code == 401
    assert "não confere" in res.json()["detail"]


def test_password_change_rejects_short_or_identical(client):
    for nova, esperado in [("curta", "pelo menos"), ("senha-forte-123", "igual")]:
        res = client.post(
            "/api/v1/auth/password",
            json={"current_password": "senha-forte-123", "new_password": nova},
        )
        assert res.status_code == 400, res.text
        assert esperado in res.json()["detail"]


def test_changing_the_password_invalidates_the_old_session(client):
    """O JWT é sem estado: sem a época, um token roubado valeria 7 dias mesmo
    depois da troca — e a troca daria uma falsa sensação de segurança."""
    antigo = client.headers["Authorization"]

    res = client.post(
        "/api/v1/auth/password",
        json={"current_password": "senha-forte-123", "new_password": "nova-senha-456"},
    )
    assert res.status_code == 200, res.text
    novos = res.json()

    # o token antigo para de valer imediatamente
    velho = client.get("/api/v1/auth/me", headers={"Authorization": antigo})
    assert velho.status_code == 401
    assert "senha foi alterada" in velho.json()["detail"]

    # o token devolvido pela troca funciona
    novo = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {novos['access_token']}"}
    )
    assert novo.status_code == 200

    # e a senha nova é a que passa a valer no login
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "senha-forte-123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "nova-senha-456"}
        ).status_code
        == 200
    )


def test_old_refresh_token_stops_working_after_the_change(client):
    """O refresh dura 7 dias: é justamente o que precisa ser cortado."""
    inicial = _logar(client)
    client.post(
        "/api/v1/auth/password",
        json={"current_password": "senha-forte-123", "new_password": "nova-senha-456"},
    )

    res = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": inicial["refresh_token"]}
    )
    assert res.status_code == 401


def test_profile_accepts_email_and_display_name(client):
    res = client.put(
        "/api/v1/auth/me",
        json={"email": "edu@exemplo.com", "display_name": "Edu"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["email"] == "edu@exemplo.com"
    assert res.json()["label"] == "Edu", "o nome de exibição vence o de usuário"

    # apagar o nome volta a mostrar o usuário
    res = client.put("/api/v1/auth/me", json={"email": "", "display_name": ""})
    assert res.json()["label"] == "admin"


def test_invalid_email_is_refused(client):
    res = client.put("/api/v1/auth/me", json={"email": "nao-e-email", "display_name": ""})
    assert res.status_code == 400
    assert "inválido" in res.json()["detail"]


def test_owner_can_reset_another_users_password(client):
    """Substituto do 'esqueci a senha': o Aether não manda e-mail."""
    novo = client.post(
        "/api/v1/users",
        json={"username": "ajudante", "password": "senha-inicial-1", "role": "moderator"},
    ).json()

    sessao = client.post(
        "/api/v1/auth/login", json={"username": "ajudante", "password": "senha-inicial-1"}
    ).json()

    res = client.post(
        f"/api/v1/users/{novo['id']}/password", json={"new_password": "redefinida-999"}
    )
    assert res.status_code == 204, res.text

    # a sessão que ele tinha aberta cai
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {sessao['access_token']}"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "ajudante", "password": "redefinida-999"}
        ).status_code
        == 200
    )
