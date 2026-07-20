"""Aether 7 Days to Die Provider.

Expõe a instância ``provider`` consumida pelo Core através do grupo de
entry points ``aether.providers``.
"""

from aether_provider_sevendays.provider import SevenDaysProvider

provider = SevenDaysProvider()

__all__ = ["SevenDaysProvider", "provider"]
