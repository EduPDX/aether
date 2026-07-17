"""Sync client protocol tests: signature verification and diff planning."""

import hashlib
import json

import pytest
from aether_sync.protocol import (
    ManifestError,
    build_plan,
    canonical_manifest_bytes,
    verify_manifest,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_manifest() -> dict:
    return {
        "version": 1,
        "instance": {"id": "i1", "name": "Srv"},
        "profile": {"id": "p1", "name": "Padrao", "channel": "stable"},
        "generated_at": "2026-07-17T00:00:00+00:00",
        "files": [
            {"path": "mods/alpha.jar", "sha256": sha(b"alpha"), "size": 5, "action": "require"},
            {"path": "mods/beta.jar", "sha256": sha(b"beta"), "size": 4, "action": "require"},
            {"path": "config/x.toml", "sha256": sha(b"[x]"), "size": 3, "action": "optional"},
        ],
        "managed": [{"dir": "mods", "patterns": ["*.jar"], "recursive": True}],
        "total_size": 12,
    }


def signed(manifest: dict) -> tuple[str, str]:
    key = Ed25519PrivateKey.generate()
    sig = key.sign(canonical_manifest_bytes(manifest)).hex()
    pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return sig, pub


def test_verify_ok_and_tamper_detected():
    manifest = make_manifest()
    sig, pub = signed(manifest)
    verify_manifest(manifest, sig, pub)  # não levanta

    tampered = json.loads(json.dumps(manifest))
    tampered["files"][0]["sha256"] = sha(b"malicioso")
    with pytest.raises(ManifestError):
        verify_manifest(tampered, sig, pub)


def test_unsupported_version_rejected():
    manifest = make_manifest()
    manifest["version"] = 99
    sig, pub = signed(manifest)
    with pytest.raises(ManifestError):
        verify_manifest(manifest, sig, pub)


def test_plan_fresh_directory_downloads_required_only(tmp_path):
    plan = build_plan(make_manifest(), tmp_path)
    assert [f["path"] for f in plan.download] == ["mods/alpha.jar", "mods/beta.jar"]
    assert plan.retire == []
    assert plan.download_size == 9


def test_plan_optional_included_when_requested(tmp_path):
    plan = build_plan(make_manifest(), tmp_path, include_optional=True)
    assert len(plan.download) == 3


def test_plan_skips_correct_files_and_redownloads_changed(tmp_path):
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "alpha.jar").write_bytes(b"alpha")  # correto
    (tmp_path / "mods" / "beta.jar").write_bytes(b"BETA")  # hash errado (mesmo tamanho)
    plan = build_plan(make_manifest(), tmp_path)
    assert [f["path"] for f in plan.download] == ["mods/beta.jar"]
    assert plan.keep == 1


def test_plan_retires_unmanaged_extras(tmp_path):
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "alpha.jar").write_bytes(b"alpha")
    (tmp_path / "mods" / "beta.jar").write_bytes(b"beta")
    (tmp_path / "mods" / "velho-mod.jar").write_bytes(b"remove-me")
    (tmp_path / "mods" / "notas.txt").write_bytes(b"nao-gerenciado")  # não bate padrão
    plan = build_plan(make_manifest(), tmp_path)
    assert plan.retire == ["mods/velho-mod.jar"]
    assert plan.is_synced is False

    (tmp_path / "mods" / "velho-mod.jar").unlink()
    assert build_plan(make_manifest(), tmp_path).is_synced is True
