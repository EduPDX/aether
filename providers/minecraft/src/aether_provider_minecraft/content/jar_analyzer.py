"""Metadata extraction from Minecraft mod ``.jar`` files.

Ported from the original GerenciadorDeMods with the same battle-tested
heuristics: Forge/NeoForge ``mods.toml`` (with a regex fallback for
malformed TOML), Fabric ``fabric.mod.json``, ``${file.jarVersion}``
resolution via ``MANIFEST.MF``, Forge-major → Minecraft-version mapping and
filename-based version guessing.

The analyzer is pure: it reads the jar and returns metadata (icon included
as bytes); it never writes to disk.
"""

import json
import re
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from aether_sdk import ContentDependency, ContentMetadata

MAX_ICON_BYTES = 3 * 1024 * 1024

# Forge major version -> Minecraft version it targets.
FORGE_TO_MC = {
    14: "1.12.2", 25: "1.13.2", 28: "1.14.4", 31: "1.15.2", 32: "1.16.1",
    34: "1.16.3", 35: "1.16.4", 36: "1.16.5", 37: "1.17.1", 39: "1.18.1",
    40: "1.18.2", 41: "1.19", 43: "1.19.2", 44: "1.19.3", 45: "1.19.4",
    46: "1.20", 47: "1.20.1", 48: "1.20.2", 49: "1.20.4", 50: "1.20.6",
    51: "1.21", 52: "1.21.1",
}  # fmt: skip

_MC_IN_FILENAME = re.compile(r"(?<![\d.])(1\.(\d{1,2})(?:\.\d{1,2})?)(?![\d])")
_RANGE = re.compile(r"[\[\(]\s*([^,\[\]\(\)]*)\s*(?:,\s*([^,\[\]\(\)]*)\s*)?[\]\)]")


def pretty_version_range(rng: Any) -> str:
    """``[1.20.1]`` → ``1.20.1``; ``[1.20,)`` → ``1.20+``; ``[a,b)`` → ``a – b``."""
    if not rng:
        return ""
    if isinstance(rng, list):
        return ", ".join(str(x) for x in rng)
    rng = str(rng).strip()
    m = _RANGE.fullmatch(rng)
    if not m:
        return rng.replace(">=", "").replace("~", "").strip()
    lo = (m.group(1) or "").strip()
    hi = (m.group(2) or "").strip() if m.group(2) is not None else None
    if hi is None or lo == hi:
        return lo
    if lo and not hi:
        return lo + "+"
    if lo and hi:
        return f"{lo} – {hi}"
    return f"≤ {hi}" if hi else rng


def _read_manifest_version(zf: zipfile.ZipFile) -> str | None:
    try:
        raw = zf.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
    except KeyError:
        return None
    m = re.search(r"^Implementation-Version:\s*(.+)$", raw, re.M)
    return m.group(1).strip() if m else None


def _toml_fallback(text: str) -> dict[str, Any]:
    """Regex extraction for malformed mods.toml files tomllib rejects."""

    def grab(key: str) -> str | None:
        for pattern in (
            r"^\s*" + key + r'\s*=\s*"""(.*?)"""',
            r"^\s*" + key + r"\s*=\s*'''(.*?)'''",
            r"^\s*" + key + r'\s*=\s*"([^"\n]*)"',
        ):
            m = re.search(pattern, text, re.S | re.M)
            if m:
                return m.group(1).strip()
        return None

    game_version = ""
    m = re.search(r'modId\s*=\s*"minecraft"[\s\S]{0,200}?versionRange\s*=\s*"([^"]+)"', text)
    if m:
        game_version = pretty_version_range(m.group(1))

    return {
        "content_id": grab("modId") or "",
        "display_name": grab("displayName"),
        "version": grab("version") or "",
        "description": grab("description") or "",
        "authors": grab("authors") or "",
        "license": grab("license") or "",
        "homepage": grab("displayURL") or "",
        "game_version": game_version,
        "logo_file": grab("logoFile"),
    }


def _parse_forge_toml(zf: zipfile.ZipFile, toml_name: str) -> dict[str, Any]:
    text = zf.read(toml_name).decode("utf-8", "replace")
    try:
        data = tomllib.loads(text)
    except Exception:
        return _toml_fallback(text)

    mods = data.get("mods") or [{}]
    mod0 = mods[0] if mods else {}
    modid = mod0.get("modId") or ""

    deps_all = data.get("dependencies") or {}
    deps = deps_all.get(modid) or []
    if not deps and deps_all:
        deps = next((v for v in deps_all.values() if isinstance(v, list)), [])

    game_version = ""
    forge_major = None
    dependencies: list[ContentDependency] = []
    for d in deps:
        if not isinstance(d, dict):
            continue
        dep_id = d.get("modId", "")
        rng = pretty_version_range(d.get("versionRange", ""))
        if dep_id.lower() == "minecraft":
            game_version = rng
        elif dep_id.lower() in ("forge", "neoforge") and forge_major is None:
            mnum = re.search(r"(\d+)", str(d.get("versionRange", "")))
            if mnum:
                forge_major = int(mnum.group(1))
        dependencies.append(
            ContentDependency(
                content_id=dep_id,
                version_range=rng,
                mandatory=bool(d.get("mandatory", d.get("type", "required") == "required")),
            )
        )

    authors = mod0.get("authors") or data.get("authors") or ""
    if isinstance(authors, list):
        authors = ", ".join(str(a) for a in authors)

    return {
        "content_id": modid,
        "display_name": mod0.get("displayName"),
        "version": str(mod0.get("version") or ""),
        "description": str(mod0.get("description") or "").strip(),
        "authors": str(authors),
        "license": str(data.get("license") or ""),
        "homepage": str(mod0.get("displayURL") or ""),
        "game_version": game_version,
        "client_only": bool(data.get("clientSideOnly") or mod0.get("clientSideOnly")),
        "dependencies": dependencies,
        "logo_file": mod0.get("logoFile") or data.get("logoFile"),
        "forge_major": forge_major,
    }


def _parse_fabric_json(zf: zipfile.ZipFile) -> dict[str, Any]:
    text = zf.read("fabric.mod.json").decode("utf-8", "replace").lstrip("﻿")
    data = json.loads(text, strict=False)

    names = []
    for a in data.get("authors") or []:
        names.append(a.get("name", "") if isinstance(a, dict) else str(a))

    depends = data.get("depends") or {}
    dependencies = [
        ContentDependency(content_id=k, version_range=pretty_version_range(v))
        for k, v in depends.items()
    ]
    contact = data.get("contact") or {}

    return {
        "content_id": data.get("id", ""),
        "display_name": data.get("name"),
        "version": str(data.get("version") or ""),
        "description": str(data.get("description") or "").strip(),
        "authors": ", ".join(n for n in names if n),
        "license": str(data.get("license") or ""),
        "homepage": contact.get("homepage") or contact.get("sources") or "",
        "game_version": pretty_version_range(depends.get("minecraft")),
        "client_only": data.get("environment") == "client",
        "dependencies": dependencies,
        "logo_file": data.get("icon"),
    }


def _extract_icon(zf: zipfile.ZipFile, logo_file: str | None, modid: str) -> bytes | None:
    candidates: list[str] = []
    if logo_file:
        candidates.append(str(logo_file).lstrip("/"))
    if modid:
        candidates += [f"assets/{modid}/icon.png", f"assets/{modid}/logo.png", f"{modid}.png"]
    candidates += ["logo.png", "icon.png", "assets/icon.png", "pack.png"]

    names = set(zf.namelist())
    for cand in candidates:
        if cand not in names:
            continue
        try:
            data = zf.read(cand)
        except Exception:
            continue
        if data and len(data) <= MAX_ICON_BYTES:
            return data
    return None


def _guess_game_version_from_filename(file_name: str) -> str:
    for m in _MC_IN_FILENAME.finditer(file_name):
        if 7 <= int(m.group(2)) <= 21:  # plausible Minecraft 1.x versions
            return m.group(1)
    return ""


class JarModAnalyzer:
    """ContentAnalyzer for Minecraft mod jars (Forge, NeoForge, Fabric)."""

    content_type = "mod"

    def analyze(self, path: Path) -> ContentMetadata:
        file_name = path.name
        fallback_name = re.sub(r"\.jar(\.disabled)?$", "", file_name, flags=re.I)
        parsed: dict[str, Any] = {}
        loader = ""
        icon: bytes | None = None
        error: str | None = None

        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                if "META-INF/mods.toml" in names:
                    loader = "Forge"
                    parsed = _parse_forge_toml(zf, "META-INF/mods.toml")
                elif "META-INF/neoforge.mods.toml" in names:
                    loader = "NeoForge"
                    parsed = _parse_forge_toml(zf, "META-INF/neoforge.mods.toml")
                elif "fabric.mod.json" in names:
                    loader = "Fabric"
                    parsed = _parse_fabric_json(zf)

                version = parsed.get("version", "")
                if not version or "${" in version:
                    version = _read_manifest_version(zf) or re.sub(r"\$\{[^}]*\}", "?", version)
                    parsed["version"] = version

                if parsed:
                    icon = _extract_icon(
                        zf, parsed.pop("logo_file", None), parsed.get("content_id", "")
                    )
        except zipfile.BadZipFile:
            error = "corrupted or invalid .jar file"
        except Exception as exc:  # noqa: BLE001 — analyzers must not raise
            error = f"failed to read jar: {exc}"

        forge_major = parsed.pop("forge_major", None)
        game_version = parsed.get("game_version", "")
        if not game_version and forge_major in FORGE_TO_MC:
            game_version = FORGE_TO_MC[forge_major]
        if not game_version or game_version.strip() in ("*", "?"):
            guessed = _guess_game_version_from_filename(file_name)
            game_version = guessed or ("any" if game_version.strip() == "*" else game_version)
        parsed["game_version"] = game_version

        if not parsed.get("display_name"):
            parsed["display_name"] = fallback_name

        return ContentMetadata(loader=loader, icon_png=icon, error=error, **parsed)
