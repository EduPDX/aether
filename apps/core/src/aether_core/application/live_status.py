"""Status ao vivo do servidor de jogo — jogadores online.

Resolve a porta publicada do jogo e chama a capability opcional
``live_status`` do provider (Server List Ping, no caso do Minecraft). É a
fonte única consumida tanto pelo status público (launcher) quanto pelo painel.
Continua agnóstico de jogo: aqui só há resolução de porta e o despacho para o
provider — nenhum protocolo específico.
"""

from __future__ import annotations

import time
from pathlib import Path

from aether_sdk import LaunchContext, SupportsContainer

from aether_core.application.ports_config import descrever

DEFAULT_GAME_PORT = 25565

# Cache curto por porta: o status é consultado com frequência (launcher +
# painel), então evita martelar o servidor de jogo a cada requisição.
_CACHE: dict[int, tuple[dict | None, float]] = {}
_TTL = 5.0


def game_port(provider, instance) -> int | None:
    """Porta TCP publicada onde os clientes conectam (info de conexão)."""
    if not isinstance(provider, SupportsContainer):
        return None
    try:
        spec = provider.container_spec(
            LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)
        )
        portas = descrever(spec, instance.provider_data)
    except Exception:  # noqa: BLE001 - provider quebrado não deve derrubar o status
        return None
    tcp = [p for p in portas if p.get("protocol") == "tcp"]
    if not tcp:
        return None
    for p in tcp:
        if p.get("container_port") == DEFAULT_GAME_PORT:
            return p.get("host_port")
    return tcp[0].get("host_port")


def live_players(provider, port: int | None) -> dict | None:
    """Jogadores online via ``live_status`` do provider. Bloqueante (socket) —
    chame com ``run_in_threadpool``. Devolve ``{online, max}`` ou ``None``."""
    if port is None:
        return None
    live = getattr(provider, "live_status", None)
    if live is None:
        return None
    now = time.monotonic()
    cached = _CACHE.get(port)
    if cached and cached[1] > now:
        result = cached[0]
    else:
        try:
            result = live("127.0.0.1", int(port))
        except Exception:  # noqa: BLE001 - falha de consulta vira "sem dados"
            result = None
        _CACHE[port] = (result, now + _TTL)
    if not result:
        return None
    return {"online": int(result.get("online", 0)), "max": int(result.get("max", 0))}
