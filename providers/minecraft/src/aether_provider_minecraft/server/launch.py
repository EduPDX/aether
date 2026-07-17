"""Builds a LaunchSpec for a Minecraft server directory.

Detection order:

1. ``provider_data["command"]`` — explicit custom command (list of args).
2. Modern Forge/NeoForge run script (``run.bat``/``run.sh``, 1.17+).
3. A server jar (``server.jar`` or ``*forge*universal*.jar`` etc.) via
   ``java -jar``.

``provider_data`` keys understood: ``command`` (list), ``java`` (path,
default ``java``), ``memory_mb`` (int), ``jar`` (explicit jar name).
"""

import re
import sys
from pathlib import Path

from aether_sdk import LaunchContext, LaunchSpec

STOP_COMMAND = "stop"

_JAR_PATTERNS = [
    re.compile(r"^server\.jar$", re.I),
    re.compile(r"forge.*universal.*\.jar$", re.I),
    re.compile(r"^(paper|purpur|spigot|craftbukkit).*\.jar$", re.I),
    re.compile(r"^minecraft_server.*\.jar$", re.I),
]


def _find_jar(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        jar = root / explicit
        return jar if jar.is_file() else None
    jars = [p.name for p in root.glob("*.jar")]
    for pattern in _JAR_PATTERNS:
        for name in jars:
            if pattern.search(name):
                return root / name
    return None


def build_launch_spec(ctx: LaunchContext) -> LaunchSpec | None:
    root = ctx.root_dir
    data = ctx.provider_data

    custom = data.get("command")
    if isinstance(custom, list) and custom:
        return LaunchSpec(
            command=[str(c) for c in custom],
            cwd=root,
            stop_command=data.get("stop_command", STOP_COMMAND),
        )

    script = root / ("run.bat" if sys.platform == "win32" else "run.sh")
    if script.is_file():
        command = (
            [str(script), "nogui"] if sys.platform == "win32" else ["sh", str(script), "nogui"]
        )
        return LaunchSpec(command=command, cwd=root, stop_command=STOP_COMMAND)

    jar = _find_jar(root, data.get("jar"))
    if jar is not None:
        java = str(data.get("java") or "java")
        memory = data.get("memory_mb")
        mem_args = [f"-Xms{memory}M", f"-Xmx{memory}M"] if memory else []
        return LaunchSpec(
            command=[java, *mem_args, "-jar", jar.name, "nogui"],
            cwd=root,
            stop_command=STOP_COMMAND,
        )

    return None
