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
    ConfigWarning,
    SupportsConfig,
)
from aether_sdk.container import (
    ContainerSpec,
    PortMapping,
    SupportsContainer,
    SupportsProvision,
    VolumeMount,
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
from aether_sdk.manifest import SDK_VERSION, IconSpec, ProviderManifest
from aether_sdk.players import (
    LIVE_ONLY,
    PlayerAction,
    PlayerEntry,
    PlayerList,
    PlayerListKind,
    SupportsPlayers,
)
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
    "ConfigWarning",
    "ConsoleCodec",
    "ConsoleLine",
    "ContainerSpec",
    "ContentAnalyzer",
    "ContentSource",
    "ContentDependency",
    "ContentMetadata",
    "ContentType",
    "GameProvider",
    "IconSpec",
    "LaunchContext",
    "LaunchSpec",
    "PortMapping",
    "ProviderManifest",
    "QuiescePlan",
    "SourceDependency",
    "SourceItem",
    "SourceVersion",
    "LIVE_ONLY",
    "PlayerAction",
    "PlayerEntry",
    "PlayerList",
    "PlayerListKind",
    "SupportsBackup",
    "SupportsPlayers",
    "SupportsConfig",
    "SupportsContainer",
    "SupportsGameMetadata",
    "SupportsLaunch",
    "SupportsProvision",
    "VolumeMount",
]
