"""API de backup: criar, listar, baixar, restaurar, apagar e agendar."""

import io
import zipfile

from conftest import create_instance


def _servidor(tmp_path, nome="srv"):
    """Instância com mundo, config e coisas que não devem entrar no backup."""
    root = tmp_path / nome
    (root / "world" / "region").mkdir(parents=True)
    (root / "world" / "level.dat").write_bytes(b"nivel-original")
    (root / "world" / "region" / "r.0.0.mca").write_bytes(b"regiao-original")
    (root / "config").mkdir()
    (root / "config" / "create.toml").write_text("velocidade=1")
    (root / "server.properties").write_text("level-name=world\nmax-players=20\n")
    (root / "mods").mkdir()
    (root / "mods" / "pesado.jar").write_bytes(b"x" * 5000)
    (root / "logs").mkdir()
    (root / "logs" / "latest.log").write_text("ruido")
    return root


def _criar(client, root, nome="Servidor"):
    res = client.post(
        "/api/v1/instances",
        json={"name": nome, "provider_id": "minecraft", "root_dir": str(root)},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_create_backup_contains_world_and_config_but_not_jars(client, tmp_path):
    root = _servidor(tmp_path)
    iid = _criar(client, root)

    res = client.post(f"/api/v1/instances/{iid}/backups", json={"note": "antes de mexer"})
    assert res.status_code == 201, res.text
    backup = res.json()
    assert backup["size_bytes"] > 0
    assert backup["kind"] == "manual"
    assert backup["note"] == "antes de mexer"

    baixado = client.get(f"/api/v1/instances/{iid}/backups/{backup['id']}/download")
    assert baixado.status_code == 200
    with zipfile.ZipFile(io.BytesIO(baixado.content)) as zf:
        nomes = set(zf.namelist())
        assert "world/level.dat" in nomes
        assert "world/region/r.0.0.mca" in nomes
        assert "config/create.toml" in nomes
        assert "server.properties" in nomes
        # grandes e reproduzíveis ficam de fora
        assert not any(n.endswith(".jar") for n in nomes)
        assert not any(n.startswith("logs/") for n in nomes)
        assert zf.read("world/level.dat") == b"nivel-original"


def test_listing_returns_policy_and_human_summary(client, tmp_path):
    iid = _criar(client, _servidor(tmp_path))
    client.post(f"/api/v1/instances/{iid}/backups", json={})

    res = client.get(f"/api/v1/instances/{iid}/backups")
    assert res.status_code == 200
    body = res.json()
    assert len(body["backups"]) == 1
    assert body["policy"] == {"schedule": "off", "keep": 7}
    # a interface mostra ao usuário o que entra no backup
    assert "world" in body["spec"]["summary"]
    assert body["spec"]["include"]


def test_restore_puts_the_old_world_back(client, tmp_path):
    root = _servidor(tmp_path)
    iid = _criar(client, root)
    backup = client.post(f"/api/v1/instances/{iid}/backups", json={}).json()

    # o mundo muda depois do backup
    (root / "world" / "level.dat").write_bytes(b"nivel-estragado")
    (root / "world" / "region" / "r.0.0.mca").unlink()

    res = client.post(f"/api/v1/instances/{iid}/backups/{backup['id']}/restore")
    assert res.status_code == 200, res.text
    assert res.json()["restored_files"] >= 3

    assert (root / "world" / "level.dat").read_bytes() == b"nivel-original"
    assert (root / "world" / "region" / "r.0.0.mca").exists()


def test_restore_creates_a_safety_backup_first(client, tmp_path):
    """Restaurar o backup errado não pode ser um caminho sem volta."""
    root = _servidor(tmp_path)
    iid = _criar(client, root)
    backup = client.post(f"/api/v1/instances/{iid}/backups", json={}).json()
    (root / "world" / "level.dat").write_bytes(b"estado-atual")

    res = client.post(f"/api/v1/instances/{iid}/backups/{backup['id']}/restore")
    seguranca_id = res.json()["safety_backup_id"]

    baixado = client.get(f"/api/v1/instances/{iid}/backups/{seguranca_id}/download")
    with zipfile.ZipFile(io.BytesIO(baixado.content)) as zf:
        assert zf.read("world/level.dat") == b"estado-atual"


def test_delete_removes_entry_and_file(client, tmp_path):
    iid = _criar(client, _servidor(tmp_path))
    backup = client.post(f"/api/v1/instances/{iid}/backups", json={}).json()

    assert client.delete(f"/api/v1/instances/{iid}/backups/{backup['id']}").status_code == 204
    assert client.get(f"/api/v1/instances/{iid}/backups").json()["backups"] == []
    assert (
        client.get(f"/api/v1/instances/{iid}/backups/{backup['id']}/download").status_code == 404
    )


def test_backup_of_another_instance_is_not_reachable(client, tmp_path):
    """Id válido não pode dar acesso ao arquivo de outra instância."""
    iid_a = _criar(client, _servidor(tmp_path, "a"), "A")
    iid_b = _criar(client, _servidor(tmp_path, "b"), "B")
    backup_a = client.post(f"/api/v1/instances/{iid_a}/backups", json={}).json()

    res = client.get(f"/api/v1/instances/{iid_b}/backups/{backup_a['id']}/download")
    assert res.status_code == 404
    assert client.delete(f"/api/v1/instances/{iid_b}/backups/{backup_a['id']}").status_code == 404


def test_policy_roundtrip(client, tmp_path):
    iid = _criar(client, _servidor(tmp_path))

    res = client.put(
        f"/api/v1/instances/{iid}/backups/policy", json={"schedule": "daily", "keep": 3}
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"schedule": "daily", "keep": 3}
    assert client.get(f"/api/v1/instances/{iid}/backups").json()["policy"]["schedule"] == "daily"


def test_invalid_schedule_is_rejected(client, tmp_path):
    iid = _criar(client, _servidor(tmp_path))
    res = client.put(
        f"/api/v1/instances/{iid}/backups/policy", json={"schedule": "sempre", "keep": 3}
    )
    assert res.status_code == 422


def test_instance_without_backup_content_fails_clearly(client, mods_dir):
    """Pasta sem mundo nenhum: erro explicando, não zip vazio."""
    iid = create_instance(client, mods_dir)
    res = client.post(f"/api/v1/instances/{iid}/backups", json={})
    assert res.status_code == 400
    assert "nada para salvar" in res.json()["detail"]
