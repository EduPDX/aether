"""Sync engine: signed manifests that clients (launcher/CLI) consume.

A *profile* holds rules describing which instance files players must (or
may) mirror. Publishing walks the files, hashes them (SHA-256), builds a
manifest and signs it with the installation's Ed25519 key. The public API
serves the manifest and — only for files listed in it — the bytes.

Manifest format (protocol v1) is the contract with clients; changes must
bump ``MANIFEST_VERSION``.
"""

import asyncio
import fnmatch
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from aether_core.application.events import EventBus
from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from aether_core.domain.instances import Instance

MANIFEST_VERSION = 1


class SyncRule(BaseModel):
    dir: str
    """Pasta de origem, relativa à raiz da instância."""
    target: str | None = None
    """Pasta de destino no cliente. ``None`` = mesma de ``dir``.

    É o que permite o perfil de cliente: os arquivos vivem em
    ``aether-client/mods`` no servidor e caem em ``mods`` no PC do jogador.
    """
    patterns: list[str] = Field(default_factory=lambda: ["*"])
    recursive: bool = True
    action: Literal["require", "optional"] = "require"

    @property
    def client_dir(self) -> str:
        return (self.target if self.target is not None else self.dir).strip("/")


class SyncRules(BaseModel):
    rules: list[SyncRule] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    """Global file-name exclusion patterns (e.g. ``*.bak``)."""


@dataclass
class SyncProfile:
    id: str
    instance_id: str
    name: str
    channel: str
    rules: SyncRules
    manifest: dict | None = None
    signature: str | None = None
    published_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(instance_id: str, name: str, channel: str, rules: SyncRules) -> "SyncProfile":
        return SyncProfile(
            id=uuid.uuid4().hex,
            instance_id=instance_id,
            name=name,
            channel=channel,
            rules=rules,
        )


class SyncProfileRepository(Protocol):
    async def add(self, profile: SyncProfile) -> None: ...

    async def get(self, profile_id: str) -> SyncProfile | None: ...

    async def list_for_instance(self, instance_id: str) -> list[SyncProfile]: ...

    async def save(self, profile: SyncProfile) -> None: ...

    async def delete(self, profile_id: str) -> bool: ...


class ManifestSigner(Protocol):
    def sign(self, payload: bytes) -> str: ...

    def public_key(self) -> str: ...


def canonical_manifest_bytes(manifest: dict) -> bytes:
    """Stable byte representation used for signing and verification."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


class SyncService:
    def __init__(
        self,
        repo: SyncProfileRepository,
        signer: ManifestSigner,
        bus: EventBus,
        providers: "ProviderRegistry | None" = None,
    ) -> None:
        self._repo = repo
        self._signer = signer
        self._bus = bus
        self._providers = providers

    # -------------------------------------------------------------- profiles --
    async def create_profile(
        self, instance: Instance, name: str, channel: str, rules: SyncRules
    ) -> SyncProfile:
        if not rules.rules:
            raise ValidationFailedError("sync rules must include at least one rule")
        profile = SyncProfile.new(instance.id, name, channel, rules)
        await self._repo.add(profile)
        await self._bus.publish("sync.profile.created", {"profile_id": profile.id})
        return profile

    async def get_profile(self, profile_id: str) -> SyncProfile:
        profile = await self._repo.get(profile_id)
        if profile is None:
            raise NotFoundError(f"sync profile not found: {profile_id}")
        return profile

    async def list_profiles(self, instance: Instance) -> list[SyncProfile]:
        return await self._repo.list_for_instance(instance.id)

    async def update_rules(self, profile_id: str, rules: SyncRules) -> SyncProfile:
        profile = await self.get_profile(profile_id)
        profile.rules = rules
        await self._repo.save(profile)
        return profile

    async def delete_profile(self, profile_id: str) -> None:
        if not await self._repo.delete(profile_id):
            raise NotFoundError(f"sync profile not found: {profile_id}")

    # --------------------------------------------------------------- publish --
    async def publish(self, instance: Instance, profile_id: str) -> SyncProfile:
        profile = await self.get_profile(profile_id)
        if profile.instance_id != instance.id:
            raise NotFoundError("profile does not belong to this instance")

        files = await asyncio.to_thread(self._collect, instance, profile.rules)
        manifest = {
            "version": MANIFEST_VERSION,
            "instance": {"id": instance.id, "name": instance.name},
            "profile": {"id": profile.id, "name": profile.name, "channel": profile.channel},
            "generated_at": datetime.now(UTC).isoformat(),
            "files": files,
            "managed": [
                {"dir": r.client_dir, "patterns": r.patterns, "recursive": r.recursive}
                for r in profile.rules.rules
                if r.action == "require"
            ],
            "total_size": sum(f["size"] for f in files),
        }
        game = await asyncio.to_thread(self._game_metadata, instance)
        if game:
            manifest["game"] = game
        profile.manifest = manifest
        profile.signature = self._signer.sign(canonical_manifest_bytes(manifest))
        profile.published_at = datetime.now(UTC)
        await self._repo.save(profile)
        await self._bus.publish("sync.published", {"profile_id": profile.id, "files": len(files)})
        return profile

    def _game_metadata(self, instance: Instance) -> dict | None:
        """Asks the provider what game build this instance runs (optional)."""
        from aether_sdk import LaunchContext, SupportsGameMetadata

        if self._providers is None:
            return instance.provider_data.get("game")
        try:
            provider = self._providers.get(instance.provider_id)
        except Exception:  # noqa: BLE001 — metadata é opcional
            return None
        if not isinstance(provider, SupportsGameMetadata):
            return instance.provider_data.get("game")
        return provider.game_metadata(
            LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)
        )

    def _collect(self, instance: Instance, rules: SyncRules) -> list[dict]:
        root = Path(instance.root_dir).resolve()
        seen: dict[str, dict] = {}
        for rule in rules.rules:
            base = (root / rule.dir).resolve()
            if base != root and root not in base.parents:
                raise ForbiddenError(f"rule dir escapes the instance root: {rule.dir}")
            if not base.is_dir():
                continue
            candidates = base.rglob("*") if rule.recursive else base.glob("*")
            for path in candidates:
                if not path.is_file():
                    continue
                name = path.name
                if any(fnmatch.fnmatch(name.lower(), p.lower()) for p in rules.exclude):
                    continue
                if not any(fnmatch.fnmatch(name.lower(), p.lower()) for p in rule.patterns):
                    continue
                source = path.relative_to(root).as_posix()
                sub = path.relative_to(base).as_posix()
                client_dir = rule.client_dir
                rel = f"{client_dir}/{sub}" if client_dir else sub
                if rel in seen:
                    continue
                seen[rel] = {
                    # 'path' é onde o arquivo cai no cliente; 'source' é onde
                    # ele está no servidor (usado só pelo download).
                    "path": rel,
                    "source": source,
                    "sha256": _sha256_file(path),
                    "size": path.stat().st_size,
                    "action": rule.action,
                }
        return sorted(seen.values(), key=lambda f: f["path"])

    # ---------------------------------------------------------------- public --
    def public_payload(self, profile: SyncProfile) -> dict:
        if profile.manifest is None or profile.signature is None:
            raise NotFoundError("profile has no published manifest")
        return {
            "manifest": profile.manifest,
            "signature": profile.signature,
            "public_key": self._signer.public_key(),
        }

    def resolve_manifest_file(
        self, instance: Instance, profile: SyncProfile, rel_path: str
    ) -> Path:
        """Only files listed in the published manifest are downloadable."""
        if profile.manifest is None:
            raise NotFoundError("profile has no published manifest")
        rel_path = rel_path.replace("\\", "/").lstrip("/")
        entry = next((f for f in profile.manifest["files"] if f["path"] == rel_path), None)
        if entry is None:
            raise NotFoundError(f"file is not part of the manifest: {rel_path}")
        # Manifestos antigos não têm 'source': o destino era a própria origem.
        full = (Path(instance.root_dir) / entry.get("source", rel_path)).resolve()
        root = Path(instance.root_dir).resolve()
        if root not in full.parents:
            raise ForbiddenError("path escapes the instance root")
        if not full.is_file():
            raise NotFoundError(f"file missing on server: {rel_path}")
        return full


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
