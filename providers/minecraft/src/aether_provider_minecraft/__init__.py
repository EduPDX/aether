"""Aether Minecraft Provider.

Exposes the ``provider`` instance consumed by the Core through the
``aether.providers`` entry-point group.
"""

from aether_provider_minecraft.provider import MinecraftProvider

provider = MinecraftProvider()

__all__ = ["MinecraftProvider", "provider"]
