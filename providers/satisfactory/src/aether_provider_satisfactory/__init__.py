"""Aether Satisfactory Provider.

Expõe a instância ``provider`` consumida pelo Core através do grupo de
entry points ``aether.providers``.
"""

from aether_provider_satisfactory.provider import SatisfactoryProvider

provider = SatisfactoryProvider()

__all__ = ["SatisfactoryProvider", "provider"]
