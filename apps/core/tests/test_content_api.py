"""Content API tests: list, toggle, trash, copy, compare, icons."""

from pathlib import Path

from conftest import create_instance, make_mod_jar


def test_list_content_with_metadata_and_icon(client, mods_dir):
    make_mod_jar(mods_dir, "alpha-1.0.jar", "alpha", "1.0.0", name="Alpha Mod", with_icon=True)
    make_mod_jar(mods_dir, "beta-2.0.jar.disabled", "beta", "2.0.0")
    iid = create_instance(client, mods_dir)

    res = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"})
    assert res.status_code == 200
    items = {i["file"]: i for i in res.json()}
    assert len(items) == 2

    alpha = items["alpha-1.0.jar"]
    assert alpha["enabled"] is True
    assert alpha["metadata"]["display_name"] == "Alpha Mod"
    assert alpha["metadata"]["version"] == "1.0.0"
    assert alpha["metadata"]["game_version"] == "1.20.1"
    assert alpha["icon_url"], "icon should have been extracted"

    icon = client.get(alpha["icon_url"])
    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/png"

    beta = items["beta-2.0.jar.disabled"]
    assert beta["enabled"] is False


def test_list_unknown_content_type_fails(client, mods_dir):
    iid = create_instance(client, mods_dir)
    res = client.get(f"/api/v1/instances/{iid}/content", params={"type": "plugin"})
    assert res.status_code == 404


def test_duplicates_are_marked(client, mods_dir):
    make_mod_jar(mods_dir, "dup-1.0.jar", "dup", "1.0.0")
    make_mod_jar(mods_dir, "dup-2.0.jar", "dup", "2.0.0")
    iid = create_instance(client, mods_dir)
    items = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    assert all(i["duplicate"] for i in items)


def test_toggle(client, mods_dir):
    make_mod_jar(mods_dir, "alpha-1.0.jar", "alpha")
    iid = create_instance(client, mods_dir)

    res = client.post(
        f"/api/v1/instances/{iid}/content/toggle",
        json={"type": "mod", "file": "alpha-1.0.jar"},
    )
    assert res.status_code == 200
    assert res.json()["file"] == "alpha-1.0.jar.disabled"
    assert not (mods_dir / "alpha-1.0.jar").exists()
    assert (mods_dir / "alpha-1.0.jar.disabled").exists()

    res = client.post(
        f"/api/v1/instances/{iid}/content/toggle",
        json={"type": "mod", "file": "alpha-1.0.jar.disabled"},
    )
    assert res.json()["file"] == "alpha-1.0.jar"

    res = client.post(
        f"/api/v1/instances/{iid}/content/toggle",
        json={"type": "mod", "file": "ghost.jar"},
    )
    assert res.status_code == 404


def test_trash_moves_file_out(client, mods_dir):
    make_mod_jar(mods_dir, "alpha-1.0.jar", "alpha")
    iid = create_instance(client, mods_dir)
    res = client.post(
        f"/api/v1/instances/{iid}/content/trash",
        json={"type": "mod", "file": "alpha-1.0.jar"},
    )
    assert res.status_code == 200
    assert not (mods_dir / "alpha-1.0.jar").exists()
    assert Path(res.json()["moved_to"]).exists()


def test_copy_between_instances(client, mods_dir, tmp_path):
    other_dir = tmp_path / "instance-b"
    other_dir.mkdir()
    make_mod_jar(mods_dir, "alpha-1.0.jar", "alpha")
    iid_a = create_instance(client, mods_dir, "A")
    iid_b = create_instance(client, other_dir, "B")

    res = client.post(
        f"/api/v1/instances/{iid_a}/content/copy",
        json={"type": "mod", "file": "alpha-1.0.jar", "to_instance_id": iid_b},
    )
    assert res.status_code == 204
    assert (other_dir / "alpha-1.0.jar").exists()


def test_compare(client, mods_dir, tmp_path):
    other_dir = tmp_path / "instance-b"
    make_mod_jar(mods_dir, "shared-1.0.jar", "shared", "1.0.0")
    make_mod_jar(mods_dir, "only-a.jar", "onlya")
    make_mod_jar(other_dir, "shared-2.0.jar", "shared", "2.0.0")
    make_mod_jar(other_dir, "only-b.jar", "onlyb")
    iid_a = create_instance(client, mods_dir, "A")
    iid_b = create_instance(client, other_dir, "B")

    res = client.get(
        f"/api/v1/instances/{iid_a}/content/compare",
        params={"with": iid_b, "type": "mod"},
    )
    assert res.status_code == 200
    body = res.json()
    assert [i["file"] for i in body["only_in_a"]] == ["only-a.jar"]
    assert [i["file"] for i in body["only_in_b"]] == ["only-b.jar"]
    assert len(body["version_diffs"]) == 1
    diff = body["version_diffs"][0]
    assert diff["content_id"] == "shared"
    assert diff["a"]["version"] == "1.0.0"
    assert diff["b"]["version"] == "2.0.0"


def test_cache_survives_relisting(client, mods_dir):
    make_mod_jar(mods_dir, "alpha-1.0.jar", "alpha")
    iid = create_instance(client, mods_dir)
    first = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    second = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    assert first == second
