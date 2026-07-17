"""Network side of the sync client: fetch manifest, download files, apply."""

import asyncio
import time
from pathlib import Path

import httpx

from aether_sync.protocol import (
    ManifestError,
    SyncPlan,
    build_plan,
    sha256_file,
    verify_manifest,
)

CONCURRENCY = 4
RETRIES = 3


async def fetch_manifest(server: str, profile_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as http:
        res = await http.get(f"{server}/api/v1/public/sync/{profile_id}")
        res.raise_for_status()
        payload = res.json()
    verify_manifest(payload["manifest"], payload["signature"], payload["public_key"])
    return payload


async def apply_plan(
    server: str,
    profile_id: str,
    target_dir: Path,
    plan: SyncPlan,
    *,
    progress=print,
) -> None:
    """Downloads every planned file (verified by SHA-256) and retires extras."""
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(timeout=None) as http:

        async def fetch_one(entry: dict) -> None:
            rel = entry["path"]
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".aether-part")
            url = f"{server}/api/v1/public/sync/{profile_id}/file"

            async with semaphore:
                for attempt in range(1, RETRIES + 1):
                    try:
                        async with http.stream("GET", url, params={"path": rel}) as res:
                            res.raise_for_status()
                            with tmp.open("wb") as f:
                                async for chunk in res.aiter_bytes(1024 * 256):
                                    f.write(chunk)
                        if sha256_file(tmp) != entry["sha256"]:
                            raise ManifestError(f"hash mismatch after download: {rel}")
                        tmp.replace(dest)
                        progress(f"  [ok] {rel}")
                        return
                    except (httpx.HTTPError, ManifestError):
                        tmp.unlink(missing_ok=True)
                        if attempt == RETRIES:
                            raise
                        await asyncio.sleep(attempt)

        await asyncio.gather(*(fetch_one(e) for e in plan.download))

    if plan.retire:
        trash = target_dir / ".aether-trash" / time.strftime("%Y%m%d-%H%M%S")
        trash.mkdir(parents=True, exist_ok=True)
        for rel in plan.retire:
            src = target_dir / rel
            dest = trash / rel.replace("/", "_")
            src.replace(dest)
            progress(f"  [rem] {rel} (movido para .aether-trash)")


async def sync(
    server: str,
    profile_id: str,
    target_dir: Path,
    *,
    include_optional: bool = False,
    check_only: bool = False,
    progress=print,
) -> SyncPlan:
    server = server.rstrip("/")
    payload = await fetch_manifest(server, profile_id)
    manifest = payload["manifest"]
    progress(
        f"Manifesto: {manifest['instance']['name']} / {manifest['profile']['name']} "
        f"({manifest['profile']['channel']}) — {len(manifest['files'])} arquivos, "
        f"assinatura OK"
    )
    plan = build_plan(manifest, target_dir, include_optional=include_optional)
    progress(
        f"Plano: {len(plan.download)} baixar ({plan.download_size / 1_048_576:.1f} MB), "
        f"{len(plan.retire)} remover, {plan.keep} já corretos"
    )
    if not check_only and not plan.is_synced:
        await apply_plan(server, profile_id, target_dir, plan, progress=progress)
        progress("Sincronização concluída.")
    elif plan.is_synced:
        progress("Nada a fazer — diretório já sincronizado.")
    return plan
