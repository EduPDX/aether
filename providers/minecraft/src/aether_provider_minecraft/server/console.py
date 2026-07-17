"""Console codec for vanilla/Forge/Fabric/Paper server logs.

Typical line: ``[12:34:56] [Server thread/INFO]: Done (12.3s)! For help, ...``
Paper adds a date variant; unknown formats degrade to raw passthrough.
"""

import re

from aether_sdk import ConsoleLine

_LINE = re.compile(
    r"^\[(?:[\d:]+)\] \[(?P<thread>[^/\]]+)/(?P<level>[A-Z]+)\]:? (?:\[(?:[^\]]+)\]: )?(?P<msg>.*)$"
)
_READY = re.compile(r"Done \([\d.,]+s?\)!")


class MinecraftConsoleCodec:
    def parse(self, raw: str) -> ConsoleLine:
        m = _LINE.match(raw)
        if not m:
            return ConsoleLine(raw=raw, message=raw)
        msg = m.group("msg")
        return ConsoleLine(
            raw=raw,
            message=msg,
            level=m.group("level"),
            ready=bool(_READY.search(msg)),
        )
