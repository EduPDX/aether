"""Instance CRUD API tests."""

from conftest import create_instance


def test_create_and_get_instance(client, mods_dir):
    iid = create_instance(client, mods_dir, name="Servidor")
    res = client.get(f"/api/v1/instances/{iid}")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Servidor"
    assert body["provider_id"] == "minecraft"
    assert body["content_dirs"] == {"mod": "."}

    listing = client.get("/api/v1/instances").json()
    assert [i["id"] for i in listing] == [iid]


def test_create_with_unknown_provider_fails(client, mods_dir):
    res = client.post(
        "/api/v1/instances",
        json={"name": "X", "provider_id": "nope", "root_dir": str(mods_dir)},
    )
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")


def test_create_with_missing_dir_fails(client, tmp_path):
    res = client.post(
        "/api/v1/instances",
        json={"name": "X", "provider_id": "minecraft", "root_dir": str(tmp_path / "nope")},
    )
    assert res.status_code == 400


def test_delete_instance(client, mods_dir):
    iid = create_instance(client, mods_dir)
    assert client.delete(f"/api/v1/instances/{iid}").status_code == 204
    assert client.get(f"/api/v1/instances/{iid}").status_code == 404
    assert client.delete(f"/api/v1/instances/{iid}").status_code == 404
