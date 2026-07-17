"""Directory browser API tests."""

from fastapi.testclient import TestClient


def test_browse_lists_only_directories(client, tmp_path):
    base = tmp_path / "browse-root"
    (base / "servers").mkdir(parents=True)
    (base / "backups").mkdir()
    (base / "readme.txt").write_text("hi")

    res = client.get("/api/v1/fs/browse", params={"path": str(base)})
    assert res.status_code == 200
    body = res.json()
    names = [e["name"] for e in body["entries"]]
    assert names == ["backups", "servers"]  # ordenado, sem o .txt
    assert body["path"] == str(base.resolve())
    assert body["parent"] == str(base.parent)


def test_browse_no_path_returns_roots(client):
    body = client.get("/api/v1/fs/browse").json()
    assert body["path"] is None
    assert len(body["entries"]) >= 1  # ao menos a home


def test_browse_bad_path_falls_back_to_roots(client):
    body = client.get("/api/v1/fs/browse", params={"path": "/nao/existe/mesmo"}).json()
    assert body["path"] is None
    assert body["entries"]


def test_browse_requires_write_permission(client, tmp_path):
    client.post(
        "/api/v1/users",
        json={"username": "viewbrowse", "password": "senha-view-123", "role": "viewer"},
    )
    viewer = TestClient(client.app)
    login = viewer.post(
        "/api/v1/auth/login", json={"username": "viewbrowse", "password": "senha-view-123"}
    ).json()
    viewer.headers["Authorization"] = f"Bearer {login['access_token']}"
    assert viewer.get("/api/v1/fs/browse", params={"path": str(tmp_path)}).status_code == 403
