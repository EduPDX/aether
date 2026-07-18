"""File upload API tests."""

from conftest import create_instance


def make_instance(client, tmp_path):
    root = tmp_path / "srv"
    (root / "mods").mkdir(parents=True)
    return create_instance(client, root), root


def test_upload_into_subfolder(client, tmp_path):
    iid, root = make_instance(client, tmp_path)
    res = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "mods"},
        files=[("uploads", ("Jade.jar", b"conteudo-do-mod", "application/java-archive"))],
    )
    assert res.status_code == 200, res.text
    assert res.json()["saved"] == [{"name": "Jade.jar", "size": 15}]
    assert (root / "mods" / "Jade.jar").read_bytes() == b"conteudo-do-mod"


def test_upload_multiple_files(client, tmp_path):
    iid, root = make_instance(client, tmp_path)
    res = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "mods"},
        files=[
            ("uploads", ("a.jar", b"aaa", "application/java-archive")),
            ("uploads", ("b.jar", b"bbbb", "application/java-archive")),
        ],
    )
    assert res.status_code == 200
    assert {s["name"] for s in res.json()["saved"]} == {"a.jar", "b.jar"}
    assert (root / "mods" / "a.jar").exists()
    assert (root / "mods" / "b.jar").exists()


def test_upload_refuses_overwrite_by_default(client, tmp_path):
    iid, root = make_instance(client, tmp_path)
    (root / "mods" / "x.jar").write_bytes(b"antigo")
    res = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "mods"},
        files=[("uploads", ("x.jar", b"novo", "application/java-archive"))],
    )
    assert res.status_code == 409
    assert (root / "mods" / "x.jar").read_bytes() == b"antigo"

    res = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "mods", "overwrite": "true"},
        files=[("uploads", ("x.jar", b"novo", "application/java-archive"))],
    )
    assert res.status_code == 200
    assert (root / "mods" / "x.jar").read_bytes() == b"novo"


def test_upload_cannot_escape_sandbox(client, tmp_path):
    iid, _ = make_instance(client, tmp_path)
    # tanto o caminho da pasta quanto o nome do arquivo são higienizados
    res = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "../fora"},
        files=[("uploads", ("x.jar", b"hack", "application/java-archive"))],
    )
    assert res.status_code in (403, 404)

    res = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "mods"},
        files=[("uploads", ("../../evil.jar", b"hack", "application/java-archive"))],
    )
    # o nome vira apenas o basename, nada escapa
    assert res.status_code == 200
    assert not (tmp_path / "evil.jar").exists()
    assert (tmp_path / "srv" / "mods" / "evil.jar").exists()


def test_upload_requires_write_permission(client, tmp_path):
    from fastapi.testclient import TestClient

    iid, _ = make_instance(client, tmp_path)
    client.post(
        "/api/v1/users",
        json={"username": "modup", "password": "senha-mod-123", "role": "moderator"},
    )
    mod = TestClient(client.app)
    login = mod.post(
        "/api/v1/auth/login", json={"username": "modup", "password": "senha-mod-123"}
    ).json()
    mod.headers["Authorization"] = f"Bearer {login['access_token']}"
    res = mod.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "mods"},
        files=[("uploads", ("x.jar", b"x", "application/java-archive"))],
    )
    assert res.status_code == 403
