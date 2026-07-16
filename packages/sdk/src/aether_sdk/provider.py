"""The provider contract (v0): identity + content analysis."""

from typing import Protocol, runtime_checkable

from aether_sdk.content import ContentAnalyzer, ContentType
from aether_sdk.manifest import ProviderManifest


@runtime_checkable
class GameProvider(Protocol):
    """Contract every game provider must satisfy.

    Discovered by the Core through the ``aether.providers`` entry-point
    group; the entry point must resolve to an *instance* implementing this
    protocol.

    ``content_analyzer`` must raise :class:`LookupError` for unknown
    content-type ids.
    """

    manifest: ProviderManifest

    def content_types(self) -> list[ContentType]: ...

    def content_analyzer(self, content_type: str) -> ContentAnalyzer: ...
