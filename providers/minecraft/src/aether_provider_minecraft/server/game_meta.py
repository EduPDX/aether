"""Detects which Minecraft build (version + mod loader) a server dir runs.

Detection order:

1. Explicit ``provider_data["game"]`` (admin override).
2. Forge/NeoForge library layout: ``libraries/net/minecraftforge/forge/
   <mc>-<forge>/`` (created by the Forge installer).
3. Version pattern in server jar names.
"""

import re
from pathlib import Path

_FORGE_DIR = re.compile(r"^([\d.]+)-([\d.]+)")
_JAR_VERSION = re.compile(r"(?:minecraft_server[._-]?|server[._-]?)?(1\.\d{1,2}(?:\.\d{1,2})?)")


def detect_game_metadata(root: Path, provider_data: dict) -> dict | None:
    explicit = provider_data.get("game")
    if isinstance(explicit, dict) and explicit.get("minecraft"):
        return explicit

    for loader, maven_path in (
        ("forge", "libraries/net/minecraftforge/forge"),
        ("neoforge", "libraries/net/neoforged/neoforge"),
    ):
        base = root / maven_path
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir(), reverse=True):
            m = _FORGE_DIR.match(child.name)
            if m:
                if loader == "neoforge":
                    # NeoForge dirs são só a versão do loader (ex.: 20.4.x)
                    return {"loader": "neoforge", "loader_version": child.name}
                return {
                    "minecraft": m.group(1),
                    "loader": loader,
                    "loader_version": m.group(2),
                }

    for jar in root.glob("*.jar"):
        m = _JAR_VERSION.search(jar.name.lower())
        if m and m.group(1).startswith("1."):
            return {"minecraft": m.group(1), "loader": "vanilla"}
    return None
