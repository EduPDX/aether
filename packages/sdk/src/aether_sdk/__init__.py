"""Aether SDK — public contracts between the Core and game providers.

Version 0 of the contract covers content analysis only (roadmap v0.1).
Lifecycle, console, config schema and sync contracts arrive in later versions.
"""

from aether_sdk.backup import BackupSpec, QuiescePlan, SupportsBackup
from aether_sdk.config import (
    ConfigCodec,
    ConfigField,
    ConfigFieldType,
    ConfigSchema,
    SupportsConfig,
)
from aether_sdk.content import (
    ContentAnalyzer,
    ContentDependency,
    ContentMetadata,
    ContentType,
)
from aether_sdk.launch import (
    ConsoleCodec,
    ConsoleLine,
    LaunchContext,
    LaunchSpec,
    SupportsGameMetadata,
    SupportsLaunch,
)
from aether_sdk.manifest import SDK_VERSION, ProviderManifest
from aether_sdk.provider import GameProvider
from aether_sdk.source import (
    ContentSource,
    SourceDependency,
    SourceItem,
    SourceVersion,
)

__all__ = [
    "SDK_VERSION",
    "BackupSpec",
    "ConfigCodec",
    "ConfigField",
    "ConfigFieldType",
    "ConfigSchema",
    "ConsoleCodec",
    "ConsoleLine",
    "ContentAnalyzer",
    "ContentSource",
    "ContentDependency",
    "ContentMetadata",
    "ContentType",
    "GameProvider",
    "LaunchContext",
    "LaunchSpec",
    "ProviderManifest",
    "QuiescePlan",
    "SourceDependency",
    "SourceItem",
    "SourceVersion",
    "SupportsBackup",
    "SupportsConfig",
    "SupportsGameMetadata",
    "SupportsLaunch",
]
