"""Content API tests: list, toggle, trash, copy, compare, icons."""

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

    # A garantia que interessa não é onde o arquivo foi parar, e sim que ele
    # aparece na lixeira e volta de lá.
    item_id = res.json()["trash_item_id"]
    itens = client.get(f"/api/v1/instances/{iid}/trash").json()["items"]
    assert [i["id"] for i in itens] == [item_id]

    client.post(f"/api/v1/instances/{iid}/trash/{item_id}/restore")
    assert (mods_dir / "alpha-1.0.jar").exists()


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


def test_compare_server_against_client_profile(client, tmp_path):
    """Diff entre os dois lados da MESMA instância.

    É como se descobre que o cliente está sem um mod que o servidor exige
    antes de o jogo crashar ao entrar no mundo.
    """
    root = tmp_path / "instancia"
    (root / "mods").mkdir(parents=True)
    (root / "aether-client" / "mods").mkdir(parents=True)
    make_mod_jar(root / "mods", "shared-1.0.jar", "shared", "1.0.0")
    make_mod_jar(root / "mods", "so-no-servidor.jar", "servidor")
    make_mod_jar(root / "aether-client" / "mods", "shared-2.0.jar", "shared", "2.0.0")
    make_mod_jar(root / "aether-client" / "mods", "so-no-cliente.jar", "cliente")

    res = client.post(
        "/api/v1/instances",
        json={"name": "Servidor", "provider_id": "minecraft", "root_dir": str(root)},
    )
    assert res.status_code == 201, res.text
    iid = res.json()["id"]

    res = client.get(
        f"/api/v1/instances/{iid}/content/compare",
        params={"with": iid, "type": "mod", "with_type": "mod_client"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [i["file"] for i in body["only_in_a"]] == ["so-no-servidor.jar"]
    assert [i["file"] for i in body["only_in_b"]] == ["so-no-cliente.jar"]
    assert len(body["version_diffs"]) == 1
    diff = body["version_diffs"][0]
    assert diff["content_id"] == "shared"
    assert (diff["a"]["version"], diff["b"]["version"]) == ("1.0.0", "2.0.0")


def test_copy_from_server_to_client_profile(client, tmp_path):
    root = tmp_path / "instancia2"
    (root / "mods").mkdir(parents=True)
    make_mod_jar(root / "mods", "levar.jar", "levar")
    res = client.post(
        "/api/v1/instances",
        json={"name": "Servidor", "provider_id": "minecraft", "root_dir": str(root)},
    )
    iid = res.json()["id"]

    res = client.post(
        f"/api/v1/instances/{iid}/content/copy",
        json={"to_instance_id": iid, "type": "mod", "to_type": "mod_client", "file": "levar.jar"},
    )
    assert res.status_code == 204, res.text
    assert (root / "aether-client" / "mods" / "levar.jar").exists()
    # o original continua no servidor: é cópia, não movimentação
    assert (root / "mods" / "levar.jar").exists()


def test_copy_into_the_same_folder_is_rejected(client, mods_dir):
    """Sem isso, copiar para o mesmo tipo na mesma instância se copiaria
    sobre si mesmo — silenciosamente ou corrompendo o arquivo."""
    make_mod_jar(mods_dir, "alpha.jar", "alpha")
    iid = create_instance(client, mods_dir)
    res = client.post(
        f"/api/v1/instances/{iid}/content/copy",
        json={"to_instance_id": iid, "type": "mod", "file": "alpha.jar"},
    )
    assert res.status_code == 400, res.text


def test_cache_survives_relisting(client, mods_dir):
    make_mod_jar(mods_dir, "alpha-1.0.jar", "alpha")
    iid = create_instance(client, mods_dir)
    first = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    second = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    assert first == second
