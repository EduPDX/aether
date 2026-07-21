"""Console de servidores Unreal Engine (Satisfactory, HumanitZ, …).

O log da UE tem um formato próprio e estável::

    [2026.07.21-12.00.05:123][  0]LogNet: Warning: alguma coisa

``[data-hora][frame]Categoria: [Severidade:] mensagem`` — a severidade só
aparece em avisos e erros; o resto é informativo. Linhas sem o prefixo (a saída
do SteamCMD durante a instalação, um stack trace) passam cruas.

Qual linha marca "servidor pronto" muda de jogo para jogo, então o padrão de
prontidão é injetado pelo provider — é a única parte que a engine não padroniza.
"""

import re

from aether_sdk.launch import ConsoleCodec, ConsoleLine

_LINHA = re.compile(
    r"^\[[\d.\-:]+\]\[\s*\d+\](?P<cat>\w+):\s*(?:(?P<sev>Error|Warning):\s*)?(?P<msg>.*)$"
)
_SEV = {"Error": "ERROR", "Warning": "WARN"}


class UnrealConsoleCodec(ConsoleCodec):
    """Codec de log da UE com marcador de prontidão configurável."""

    def __init__(self, ready_pattern: str = "") -> None:
        # Sem padrão de prontidão o estado do servidor fica por conta do
        # supervisor (processo vivo = rodando); o marcador é um extra.
        self._ready = re.compile(ready_pattern, re.IGNORECASE) if ready_pattern else None

    def parse(self, raw: str) -> ConsoleLine:
        pronto = bool(self._ready and self._ready.search(raw))
        m = _LINHA.match(raw)
        if not m:
            return ConsoleLine(raw=raw, message=raw, ready=pronto)
        return ConsoleLine(
            raw=raw,
            message=f"{m.group('cat')}: {m.group('msg')}",
            level=_SEV.get(m.group("sev"), "INFO"),
            ready=pronto,
        )
