"""Provider discovery through the ``aether.providers`` entry-point group."""

import logging
from functools import lru_cache
from importlib.metadata import entry_points

from aether_sdk import GameProvider

log = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "aether.providers"


@lru_cache(maxsize=1)
def discover_providers() -> dict[str, GameProvider]:
    """Load every installed provider, keyed by manifest id.

    A broken provider is logged and skipped — one bad plugin must never
    take the Core down.
    """
    found: dict[str, GameProvider] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            provider = ep.load()
            if not isinstance(provider, GameProvider):
                raise TypeError(f"entry point {ep.name!r} does not satisfy GameProvider")
            found[provider.manifest.id] = provider
        except Exception:  # noqa: BLE001 — isolate faulty plugins
            log.exception("failed to load provider from entry point %r", ep.name)
    return found
