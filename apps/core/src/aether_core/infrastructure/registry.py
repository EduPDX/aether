"""Provider registry backed by entry-point discovery."""

from aether_sdk import GameProvider

from aether_core.domain.errors import ProviderNotFoundError
from aether_core.infrastructure.plugins import discover_providers


class EntryPointProviderRegistry:
    def get(self, provider_id: str) -> GameProvider:
        provider = discover_providers().get(provider_id)
        if provider is None:
            raise ProviderNotFoundError(f"provider not installed: {provider_id}")
        return provider

    def all(self) -> dict[str, GameProvider]:
        return dict(discover_providers())
