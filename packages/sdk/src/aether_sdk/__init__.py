"""Aether SDK — public contracts between the Core and game providers.

Version 0 of the contract covers content analysis only (roadmap v0.1).
Lifecycle, console, config schema and sync contracts arrive in later versions.
"""

from aether_sdk.content import (
    ContentAnalyzer,
    ContentDependency,
    ContentMetadata,
    ContentType,
)
from aether_sdk.manifest import SDK_VERSION, ProviderManifest
from aether_sdk.provider import GameProvider

__all__ = [
    "SDK_VERSION",
    "ContentAnalyzer",
    "ContentDependency",
    "ContentMetadata",
    "ContentType",
    "GameProvider",
    "ProviderManifest",
]
