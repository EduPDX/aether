"""Manifest verification and local diff planning (pure logic, no network)."""

import fnmatch
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SUPPORTED_MANIFEST_VERSION = 1


class ManifestError(Exception):
    pass


def canonical_manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def verify_manifest(manifest: dict, signature_hex: str, public_key_hex: str) -> None:
    """Raises ManifestError when the signature or version is invalid."""
    if manifest.get("version") != SUPPORTED_MANIFEST_VERSION:
        raise ManifestError(f"unsupported manifest version: {manifest.get('version')}")
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), canonical_manifest_bytes(manifest))
    except (InvalidSignature, ValueError) as exc:
        raise ManifestError("manifest signature verification failed") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class SyncPlan:
    download: list[dict] = field(default_factory=list)
    """Manifest entries missing locally or with a different hash."""
    retire: list[str] = field(default_factory=list)
    """Local files inside managed dirs that are not in the manifest."""
    keep: int = 0

    @property
    def download_size(self) -> int:
        return sum(f["size"] for f in self.download)

    @property
    def is_synced(self) -> bool:
        return not self.download and not self.retire


def build_plan(manifest: dict, target_dir: Path, *, include_optional: bool = False) -> SyncPlan:
    """Compares the manifest with ``target_dir`` and returns what to do."""
    plan = SyncPlan()
    wanted: dict[str, dict] = {}
    for entry in manifest["files"]:
        if entry["action"] == "optional" and not include_optional:
            continue
        wanted[entry["path"]] = entry

    for rel, entry in wanted.items():
        local = target_dir / rel
        if (
            local.is_file()
            and local.stat().st_size == entry["size"]
            and sha256_file(local) == entry["sha256"]
        ):
            plan.keep += 1
            continue
        plan.download.append(entry)

    manifest_paths = {e["path"] for e in manifest["files"]}
    for managed in manifest.get("managed", []):
        base = target_dir / managed["dir"]
        if not base.is_dir():
            continue
        candidates = base.rglob("*") if managed.get("recursive", True) else base.glob("*")
        for path in candidates:
            if not path.is_file():
                continue
            if not any(fnmatch.fnmatch(path.name.lower(), p.lower()) for p in managed["patterns"]):
                continue
            rel = path.relative_to(target_dir).as_posix()
            if rel not in manifest_paths:
                plan.retire.append(rel)

    plan.retire.sort()
    return plan
