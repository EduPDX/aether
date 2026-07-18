"""Sync engine API tests: profiles, signed manifests, public CDN."""

import hashlib

from conftest import create_instance
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

RULES = {
    "rules": [
        {"dir": "mods", "patterns": ["*.jar"], "action": "require"},
        {"dir": "config", "patterns": ["*"], "action": "optional"},
    ],
    "exclude": ["*.bak"],
}


def make_synced_instance(client, tmp_path):
    root = tmp_path / "srv"
    (root / "mods").mkdir(parents=True)
    (root / "config" / "sub").mkdir(parents=True)
    (root / "mods" / "alpha.jar").write_bytes(b"alpha-bytes")
    (root / "mods" / "beta.jar").write_bytes(b"beta-bytes")
    (root / "mods" / "backup.bak").write_bytes(b"ignore me")
    (root / "config" / "sub" / "x.toml").write_bytes(b"[a]\n")
    (root / "server.properties").write_bytes(b"secret=yes")  # fora das regras
    iid = create_instance(client, root)
    return iid, root


def create_and_publish(client, iid) -> str:
    res = client.post(
        f"/api/v1/instances/{iid}/sync-profiles",
        json={"name": "Padrao", "channel": "stable", "rules": RULES},
    )
    assert res.status_code == 201, res.text
    pid = res.json()["id"]
    res = client.post(f"/api/v1/instances/{iid}/sync-profiles/{pid}/publish")
    assert res.status_code == 200, res.text
    return pid


def test_publish_builds_correct_manifest(client, tmp_path):
    iid, root = make_synced_instance(client, tmp_path)
    pid = create_and_publish(client, iid)

    payload = client.get(f"/api/v1/public/sync/{pid}").json()
    manifest = payload["manifest"]

    paths = {f["path"]: f for f in manifest["files"]}
    assert set(paths) == {"mods/alpha.jar", "mods/beta.jar", "config/sub/x.toml"}
    assert paths["mods/alpha.jar"]["action"] == "require"
    assert paths["config/sub/x.toml"]["action"] == "optional"
    # hash bate com o conteúdo real
    expected = hashlib.sha256(b"alpha-bytes").hexdigest()
    assert paths["mods/alpha.jar"]["sha256"] == expected
    assert manifest["managed"] == [{"dir": "mods", "patterns": ["*.jar"], "recursive": True}]


def test_manifest_signature_is_valid_ed25519(client, tmp_path):
    from aether_core.application.sync import canonical_manifest_bytes

    iid, _ = make_synced_instance(client, tmp_path)
    pid = create_and_publish(client, iid)
    payload = client.get(f"/api/v1/public/sync/{pid}").json()

    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(payload["public_key"]))
    key.verify(
        bytes.fromhex(payload["signature"]),
        canonical_manifest_bytes(payload["manifest"]),
    )  # levanta InvalidSignature se estiver errado

    # adulterar o manifesto quebra a assinatura
    import pytest
    from cryptography.exceptions import InvalidSignature

    tampered = dict(payload["manifest"], total_size=999999)
    with pytest.raises(InvalidSignature):
        key.verify(bytes.fromhex(payload["signature"]), canonical_manifest_bytes(tampered))


def test_public_endpoints_require_no_auth(client, tmp_path):
    from fastapi.testclient import TestClient

    iid, _ = make_synced_instance(client, tmp_path)
    pid = create_and_publish(client, iid)

    anon = TestClient(client.app)
    assert anon.get(f"/api/v1/public/sync/{pid}").status_code == 200
    assert anon.get(f"/api/v1/public/instances/{iid}/status").status_code == 200
    res = anon.get(f"/api/v1/public/sync/{pid}/file", params={"path": "mods/alpha.jar"})
    assert res.status_code == 200
    assert res.content == b"alpha-bytes"


def test_cdn_only_serves_manifest_files(client, tmp_path):
    iid, _ = make_synced_instance(client, tmp_path)
    pid = create_and_publish(client, iid)

    for evil in ("server.properties", "../fora.txt", "..\\fora.txt", "mods/../server.properties"):
        res = client.get(f"/api/v1/public/sync/{pid}/file", params={"path": evil})
        assert res.status_code in (403, 404), evil


def test_unpublished_profile_has_no_manifest(client, tmp_path):
    iid, _ = make_synced_instance(client, tmp_path)
    res = client.post(
        f"/api/v1/instances/{iid}/sync-profiles",
        json={"name": "Rascunho", "channel": "beta", "rules": RULES},
    )
    pid = res.json()["id"]
    assert client.get(f"/api/v1/public/sync/{pid}").status_code == 404


def test_republish_reflects_changes(client, tmp_path):
    iid, root = make_synced_instance(client, tmp_path)
    pid = create_and_publish(client, iid)

    (root / "mods" / "gamma.jar").write_bytes(b"gamma!")
    (root / "mods" / "alpha.jar").unlink()
    client.post(f"/api/v1/instances/{iid}/sync-profiles/{pid}/publish")

    manifest = client.get(f"/api/v1/public/sync/{pid}").json()["manifest"]
    paths = {f["path"] for f in manifest["files"]}
    assert "mods/gamma.jar" in paths
    assert "mods/alpha.jar" not in paths


def test_sync_forbidden_for_moderator(client, tmp_path):
    from fastapi.testclient import TestClient

    iid, _ = make_synced_instance(client, tmp_path)
    client.post(
        "/api/v1/users",
        json={"username": "mod3", "password": "senha-mod-123", "role": "moderator"},
    )
    mod = TestClient(client.app)
    login = mod.post(
        "/api/v1/auth/login", json={"username": "mod3", "password": "senha-mod-123"}
    ).json()
    mod.headers["Authorization"] = f"Bearer {login['access_token']}"
    assert mod.get(f"/api/v1/instances/{iid}/sync-profiles").status_code == 403


def test_manifest_includes_game_metadata(client, tmp_path):
    root = tmp_path / "srv2"
    (root / "mods").mkdir(parents=True)
    (root / "mods" / "m.jar").write_bytes(b"m")
    forge = root / "libraries" / "net" / "minecraftforge" / "forge" / "1.20.1-47.2.0"
    forge.mkdir(parents=True)
    iid = create_instance(client, root)

    res = client.post(
        f"/api/v1/instances/{iid}/sync-profiles",
        json={"name": "ComJogo", "channel": "stable", "rules": RULES},
    )
    pid = res.json()["id"]
    client.post(f"/api/v1/instances/{iid}/sync-profiles/{pid}/publish")

    manifest = client.get(f"/api/v1/public/sync/{pid}").json()["manifest"]
    assert manifest["game"] == {
        "minecraft": "1.20.1",
        "loader": "forge",
        "loader_version": "47.2.0",
    }


def test_client_profile_maps_source_dir_to_client_dir(client, tmp_path):
    """Perfil de cliente: arquivos de aether-client/mods caem em mods/."""
    root = tmp_path / "srv-cliente"
    (root / "aether-client" / "mods").mkdir(parents=True)
    (root / "mods").mkdir()
    (root / "aether-client" / "mods" / "Jade.jar").write_bytes(b"mod-do-cliente")
    (root / "mods" / "spark.jar").write_bytes(b"so-do-servidor")
    iid = create_instance(client, root)

    res = client.post(
        f"/api/v1/instances/{iid}/sync-profiles",
        json={
            "name": "Jogadores",
            "channel": "stable",
            "rules": {
                "rules": [
                    {
                        "dir": "aether-client/mods",
                        "target": "mods",
                        "patterns": ["*.jar"],
                        "action": "require",
                    }
                ],
                "exclude": [],
            },
        },
    )
    pid = res.json()["id"]
    client.post(f"/api/v1/instances/{iid}/sync-profiles/{pid}/publish")

    manifest = client.get(f"/api/v1/public/sync/{pid}").json()["manifest"]
    paths = {f["path"] for f in manifest["files"]}
    # o jogador recebe em mods/, não em aether-client/mods/
    assert paths == {"mods/Jade.jar"}
    # o mod exclusivo do servidor não vai junto
    assert not any("spark" in p for p in paths)
    # a pasta gerenciada (para aposentar extras) é a do cliente
    assert manifest["managed"][0]["dir"] == "mods"

    # o download resolve de volta para o arquivo real no servidor
    dl = client.get(f"/api/v1/public/sync/{pid}/file", params={"path": "mods/Jade.jar"})
    assert dl.status_code == 200
    assert dl.content == b"mod-do-cliente"
