"""Lixeira: guardar com a origem, restaurar, apagar de vez e limpar."""

from datetime import UTC, datetime, timedelta

from aether_core.domain.trash import (
    TrashItem,
    TrashOrigin,
    select_for_pruning,
    stored_name_for,
)
from conftest import create_instance


def apagar(client, iid, caminho):
    """Apaga pelo explorador — o caminho que leva um item à lixeira."""
    return client.post(
        f"/api/v1/instances/{iid}/files/op",
        json={"op": "delete", "path": caminho},
    )


def make_instance(client, tmp_path):
    root = tmp_path / "srv"
    (root / "mods").mkdir(parents=True)
    (root / "world" / "region").mkdir(parents=True)
    (root / "world" / "level.dat").write_bytes(b"mundo-real")
    (root / "mods" / "algum.jar").write_bytes(b"x" * 100)
    (root / "server.properties").write_text("level-name=world\n")
    return create_instance(client, root), root


# ------------------------------------------------------------------ domínio --


def test_stored_name_keeps_items_with_the_same_name_apart():
    """A versão anterior resolvia colisão com `.1`, estragando a extensão."""
    a = stored_name_for("mod.jar", "aaaaaaaa")
    b = stored_name_for("mod.jar", "bbbbbbbb")
    assert a != b
    assert a.endswith("mod.jar") and b.endswith("mod.jar")


def _item(id_, dias, tamanho=0):
    return TrashItem(
        id=id_,
        instance_id="i",
        original_path=f"{id_}.txt",
        stored_name=id_,
        is_dir=False,
        size_bytes=tamanho,
        origin=TrashOrigin.FILES,
        trashed_at=datetime.now(UTC) - timedelta(days=dias),
    )


def test_pruning_removes_by_age():
    agora = datetime.now(UTC)
    alvos = select_for_pruning([_item("velho", 40), _item("novo", 2)], agora, dias=30)
    assert [i.id for i in alvos] == ["velho"]


def test_pruning_frees_space_starting_from_the_oldest():
    """Quem apagou há pouco tem muito mais chance de querer de volta.

    Somam 1000 num teto de 900: basta sacrificar o mais antigo, e os dois
    recentes ficam.
    """
    agora = datetime.now(UTC)
    itens = [_item("a", 10, 600), _item("b", 5, 300), _item("c", 1, 100)]
    alvos = select_for_pruning(itens, agora, dias=30, teto=900)
    assert [i.id for i in alvos] == ["a"]


def test_pruning_keeps_cutting_until_it_fits():
    """Um item só pode não bastar."""
    agora = datetime.now(UTC)
    itens = [_item("a", 10, 600), _item("b", 5, 600), _item("c", 1, 600)]
    alvos = select_for_pruning(itens, agora, dias=30, teto=1000)
    # dois de 600 já estouram o teto, então só o mais recente sobrevive
    assert [i.id for i in alvos] == ["a", "b"]


def test_pruning_leaves_everything_when_it_fits():
    agora = datetime.now(UTC)
    itens = [_item("a", 1, 10), _item("b", 2, 10)]
    assert select_for_pruning(itens, agora, dias=30, teto=1000) == []


# ------------------------------------------------------------------- rotas --


def test_deleted_file_shows_up_in_the_trash(client, tmp_path):
    iid, _ = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")

    dados = client.get(f"/api/v1/instances/{iid}/trash").json()
    assert len(dados["items"]) == 1
    item = dados["items"][0]
    assert item["name"] == "algum.jar"
    assert item["original_path"] == "mods/algum.jar"
    assert item["size_bytes"] == 100


def test_restore_puts_the_file_back_where_it_was(client, tmp_path):
    """O motivo de a lixeira existir: desfazer.

    A primeira versão guardava só o nome do arquivo, então esta operação era
    impossível — não havia registro de qual pasta era a dele.
    """
    iid, root = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")
    assert not (root / "mods" / "algum.jar").exists()

    item = client.get(f"/api/v1/instances/{iid}/trash").json()["items"][0]
    res = client.post(f"/api/v1/instances/{iid}/trash/{item['id']}/restore")

    assert res.status_code == 200
    assert res.json()["restored_to"] == "mods/algum.jar"
    assert (root / "mods" / "algum.jar").read_bytes() == b"x" * 100
    assert client.get(f"/api/v1/instances/{iid}/trash").json()["items"] == []


def test_restore_recreates_the_folder_when_it_is_gone(client, tmp_path):
    """Apagar o arquivo e depois a pasta é um caminho normal até aqui."""
    iid, root = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")
    item = client.get(f"/api/v1/instances/{iid}/trash").json()["items"][0]
    (root / "mods").rmdir()

    client.post(f"/api/v1/instances/{iid}/trash/{item['id']}/restore")
    assert (root / "mods" / "algum.jar").exists()


def test_restore_refuses_to_overwrite(client, tmp_path):
    """Um arquivo novo no mesmo caminho não pode ser atropelado pelo antigo."""
    iid, root = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")
    (root / "mods").mkdir(exist_ok=True)
    (root / "mods" / "algum.jar").write_bytes(b"versao-nova")

    item = client.get(f"/api/v1/instances/{iid}/trash").json()["items"][0]
    res = client.post(f"/api/v1/instances/{iid}/trash/{item['id']}/restore")

    assert res.status_code == 409
    assert (root / "mods" / "algum.jar").read_bytes() == b"versao-nova"


def test_folder_goes_to_the_trash_whole_and_comes_back(client, tmp_path):
    iid, root = make_instance(client, tmp_path)
    apagar(client, iid, "world")
    assert not (root / "world").exists()

    item = client.get(f"/api/v1/instances/{iid}/trash").json()["items"][0]
    assert item["is_dir"] is True

    client.post(f"/api/v1/instances/{iid}/trash/{item['id']}/restore")
    assert (root / "world" / "level.dat").read_bytes() == b"mundo-real"


def test_purge_removes_for_good(client, tmp_path):
    iid, _ = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")
    item = client.get(f"/api/v1/instances/{iid}/trash").json()["items"][0]

    assert client.delete(f"/api/v1/instances/{iid}/trash/{item['id']}").status_code == 204
    assert client.get(f"/api/v1/instances/{iid}/trash").json()["items"] == []
    # e restaurar depois disso não encontra nada
    assert client.post(f"/api/v1/instances/{iid}/trash/{item['id']}/restore").status_code == 404


def test_empty_clears_everything(client, tmp_path):
    iid, _ = make_instance(client, tmp_path)
    for alvo in ("mods/algum.jar", "server.properties"):
        apagar(client, iid, alvo)

    res = client.delete(f"/api/v1/instances/{iid}/trash")
    assert res.json()["removed"] == 2
    assert client.get(f"/api/v1/instances/{iid}/trash").json()["items"] == []


def test_two_files_with_the_same_name_both_survive(client, tmp_path):
    """Antes o segundo virava `algum.jar.1` e perdia a extensão."""
    iid, root = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")
    (root / "mods").mkdir(exist_ok=True)
    (root / "mods" / "algum.jar").write_bytes(b"segunda-versao")
    apagar(client, iid, "mods/algum.jar")

    itens = client.get(f"/api/v1/instances/{iid}/trash").json()["items"]
    assert len(itens) == 2
    assert {i["name"] for i in itens} == {"algum.jar"}


def test_trash_of_one_instance_is_invisible_to_another(client, tmp_path):
    """O id do item não pode servir para mexer na lixeira alheia."""
    iid_a, _ = make_instance(client, tmp_path / "a")
    iid_b, _ = make_instance(client, tmp_path / "b")
    apagar(client, iid_a, "mods/algum.jar")
    item = client.get(f"/api/v1/instances/{iid_a}/trash").json()["items"][0]

    assert client.get(f"/api/v1/instances/{iid_b}/trash").json()["items"] == []
    assert client.post(f"/api/v1/instances/{iid_b}/trash/{item['id']}/restore").status_code == 404
    assert client.delete(f"/api/v1/instances/{iid_b}/trash/{item['id']}").status_code == 404


def test_item_removed_by_hand_disappears_from_the_list(client, tmp_path, monkeypatch):
    """Limpar a pasta por SSH não pode deixar um 'restaurar' que quebra.

    Aconteceu de verdade: a lixeira de produção foi esvaziada à mão.
    """
    import shutil

    iid, _ = make_instance(client, tmp_path)
    apagar(client, iid, "mods/algum.jar")
    assert len(client.get(f"/api/v1/instances/{iid}/trash").json()["items"]) == 1

    from aether_core.interfaces.http import deps  # noqa: F401

    trash_root = client.app.state.settings.trash_dir
    shutil.rmtree(trash_root / iid)

    assert client.get(f"/api/v1/instances/{iid}/trash").json()["items"] == []
