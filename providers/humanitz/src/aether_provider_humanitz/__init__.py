"""Aether HumanitZ Provider.

Expõe a instância ``provider`` consumida pelo Core através do grupo de
entry points ``aether.providers``.
"""

from aether_provider_humanitz.provider import HumanitZProvider

provider = HumanitZProvider()

__all__ = ["HumanitZProvider", "provider"]
