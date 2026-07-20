"""Codec do console do 7 Days to Die (log do Unity).

Linha típica::

    2026-07-19T21:30:05 55.196 INF GameServer.Init successful

``<timestamp> <uptime> <nível> <mensagem>`` — níveis INF/WRN/ERR. Linhas fora
do padrão (saída do SteamCMD durante a instalação, stack traces do Unity)
passam cruas, sem nível.
"""

import re

from aether_sdk import ConsoleLine

_LINE = re.compile(r"^(?P<ts>\S+)\s+(?P<uptime>[\d.,]+)\s+(?P<level>INF|WRN|ERR)\s+(?P<msg>.*)$")
_READY = re.compile(r"GameServer\.Init successful")

_NIVEIS = {"INF": "INFO", "WRN": "WARN", "ERR": "ERROR"}


class SevenDaysConsoleCodec:
    def parse(self, raw: str) -> ConsoleLine:
        m = _LINE.match(raw)
        if not m:
            return ConsoleLine(raw=raw, message=raw)
        msg = m.group("msg")
        return ConsoleLine(
            raw=raw,
            message=msg,
            level=_NIVEIS.get(m.group("level"), m.group("level")),
            ready=bool(_READY.search(msg)),
        )
