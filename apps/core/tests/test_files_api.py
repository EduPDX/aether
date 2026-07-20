"""File explorer API tests: sandbox, CRUD, trash, limits."""

from pathlib import Path

from conftest import create_instance


def make_instance_with_files(client, tmp_path) -> tuple[str, Path]:
    root = tmp_path / "srv"
    (root / "config").mkdir(parents=True)
    (root / "server.properties").write_text("motd=Hello\n", encoding="utf-8", newline="\n")
    (root / "config" / "mod.toml").write_text(
        "[general]\nvalue = 1\n", encoding="utf-8", newline="\n"
    )
    (root / "big.bin").write_bytes(b"\x00" * 100)
    iid = create_instance(client, root)
    return iid, root


def test_list_and_navigate(client, tmp_path):
    iid, _ = make_instance_with_files(client, tmp_path)
    res = client.get(f"/api/v1/instances/{iid}/files")
    assert res.status_code == 200
    names = [e["name"] for e in res.json()]
    assert names[0] == "config"  # pastas primeiro
    assert "server.properties" in names

    sub = client.get(f"/api/v1/instances/{iid}/files", params={"path": "config"}).json()
    assert [e["name"] for e in sub] == ["mod.toml"]


def test_read_write_roundtrip(client, tmp_path):
    iid, root = make_instance_with_files(client, tmp_path)
    res = client.get(f"/api/v1/instances/{iid}/files/content", params={"path": "server.properties"})
    assert res.json()["content"] == "motd=Hello\n"

    res = client.put(
        f"/api/v1/instances/{iid}/files/content",
        json={"path": "server.properties", "content": "motd=Novo\n"},
    )
    assert res.status_code == 204
    assert (root / "server.properties").read_text() == "motd=Novo\n"


def test_binary_file_rejected(client, tmp_path):
    iid, _ = make_instance_with_files(client, tmp_path)
    res = client.get(f"/api/v1/instances/{iid}/files/content", params={"path": "big.bin"})
    assert res.status_code == 400


def test_path_traversal_blocked(client, tmp_path):
    iid, _ = make_instance_with_files(client, tmp_path)
    for evil in ("../fora.txt", "..\\fora.txt", "config/../../fora.txt"):
        res = client.get(f"/api/v1/instances/{iid}/files/content", params={"path": evil})
        assert res.status_code in (403, 404), evil
        res = client.put(
            f"/api/v1/instances/{iid}/files/content",
            json={"path": evil, "content": "hack"},
        )
        assert res.status_code == 403, evil
    assert not (tmp_path / "fora.txt").exists()


def test_mkdir_rename_delete(client, tmp_path):
    iid, root = make_instance_with_files(client, tmp_path)
    base = f"/api/v1/instances/{iid}/files/op"

    assert client.post(base, json={"op": "mkdir", "path": "backups"}).status_code == 200
    assert (root / "backups").is_dir()

    assert (
        client.post(
            base, json={"op": "rename", "path": "backups", "new_name": "old-backups"}
        ).status_code
        == 200
    )
    assert (root / "old-backups").is_dir()

    res = client.post(base, json={"op": "delete", "path": "old-backups"})
    assert res.status_code == 200
    assert not (root / "old-backups").exists()
    assert Path(res.json()["moved_to"]).exists()  # foi para a lixeira

    # raiz é intocável
    assert client.post(base, json={"op": "delete", "path": ""}).status_code == 403


def test_files_forbidden_for_moderator(client, tmp_path):
    from fastapi.testclient import TestClient

    iid, _ = make_instance_with_files(client, tmp_path)
    client.post(
        "/api/v1/users",
        json={"username": "mod2", "password": "senha-mod-123", "role": "moderator"},
    )
    mod = TestClient(client.app)
    login = mod.post(
        "/api/v1/auth/login", json={"username": "mod2", "password": "senha-mod-123"}
    ).json()
    mod.headers["Authorization"] = f"Bearer {login['access_token']}"
    assert mod.get(f"/api/v1/instances/{iid}/files").status_code == 403


def _instancia_com_mundo(client, tmp_path, nome="mundo-grande"):
    root = tmp_path / nome
    (root / "world" / "region").mkdir(parents=True)
    for i in range(12):
        (root / "world" / "region" / f"r.{i}.0.mca").write_bytes(bytes(range(256)) * 400)
    (root / "world" / "level.dat").write_bytes(b"nivel")
    (root / "world" / "sub" / "fundo").mkdir(parents=True)
    (root / "world" / "sub" / "fundo" / "profundo.dat").write_bytes(b"profundo")
    res = client.post(
        "/api/v1/instances",
        json={"name": "Srv", "provider_id": "minecraft", "root_dir": str(root)},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"], root


def test_folder_download_streams_a_valid_zip(client, tmp_path):
    """Regressão: pastas grandes não baixavam.

    O zip inteiro era montado em disco antes do primeiro byte e depois
    materializado na memória do navegador. Agora sai em fluxo.
    """
    import io
    import zipfile

    iid, _ = _instancia_com_mundo(client, tmp_path)
    res = client.get(f"/api/v1/instances/{iid}/files/download", params={"path": "world"})

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert 'filename="world.zip"' in res.headers["content-disposition"]
    # sem content-length: o tamanho não é conhecido antes de gerar
    assert "content-length" not in {k.lower() for k in res.headers}

    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert zf.testzip() is None, "zip íntegro"
        nomes = set(zf.namelist())
        assert "world/level.dat" not in nomes, "os caminhos são relativos à pasta baixada"
        assert "level.dat" in nomes
        assert "sub/fundo/profundo.dat" in nomes
        assert len([n for n in nomes if n.endswith(".mca")]) == 12
        assert zf.read("sub/fundo/profundo.dat") == b"profundo"


def test_download_token_allows_browser_navigation(client, tmp_path):
    iid, _ = _instancia_com_mundo(client, tmp_path, "com-token")

    res = client.post(f"/api/v1/instances/{iid}/files/download-token", params={"path": "world"})
    assert res.status_code == 200
    token = res.json()["token"]

    # sem cabeçalho de autorização, como faz uma navegação do navegador
    semtoken = client.get(
        f"/api/v1/instances/{iid}/files/download",
        params={"path": "world"},
        headers={"Authorization": ""},
    )
    assert semtoken.status_code == 401

    comtoken = client.get(
        f"/api/v1/instances/{iid}/files/download",
        params={"path": "world", "token": token},
        headers={"Authorization": ""},
    )
    assert comtoken.status_code == 200


def test_download_token_is_bound_to_its_path(client, tmp_path):
    """O token não pode virar uma chave genérica de leitura de arquivos."""
    iid, root = _instancia_com_mundo(client, tmp_path, "preso")
    (root / "segredo.txt").write_text("nao deveria vazar")

    token = client.post(
        f"/api/v1/instances/{iid}/files/download-token", params={"path": "world"}
    ).json()["token"]

    res = client.get(
        f"/api/v1/instances/{iid}/files/download",
        params={"path": "segredo.txt", "token": token},
        headers={"Authorization": ""},
    )
    assert res.status_code == 401
