"""Minecraft provider implementation (content analysis + server launch)."""

from pathlib import Path

from aether_sdk import (
    BackupSpec,
    ConfigCodec,
    ConfigSchema,
    ConsoleCodec,
    ContentAnalyzer,
    ContentType,
    LaunchContext,
    LaunchSpec,
    ProviderManifest,
    QuiescePlan,
)

from aether_provider_minecraft.content.jar_analyzer import JarModAnalyzer
from aether_provider_minecraft.server.backup import backup_spec, quiesce_plan
from aether_provider_minecraft.server.console import MinecraftConsoleCodec
from aether_provider_minecraft.server.game_meta import detect_game_metadata
from aether_provider_minecraft.server.launch import build_launch_spec
from aether_provider_minecraft.server.properties import (
    SERVER_PROPERTIES_SCHEMA,
    PropertiesCodec,
)

MANIFEST = ProviderManifest(
    id="minecraft",
    name="Minecraft",
    version="0.1.0.dev0",
    games=["minecraft-java"],
)

CONTENT_TYPES = [
    ContentType(
        id="mod",
        label="Mods do servidor",
        file_patterns=["*.jar", "*.jar.disabled"],
        default_directory="mods",
    ),
    # Perfil do cliente: mods que os jogadores recebem via launcher. Vive
    # dentro da própria instância, ao lado dos mods do servidor.
    ContentType(
        id="mod_client",
        label="Mods do cliente",
        file_patterns=["*.jar", "*.jar.disabled"],
        default_directory="aether-client/mods",
    ),
]


class MinecraftProvider:
    manifest = MANIFEST

    def __init__(self) -> None:
        self._analyzers: dict[str, ContentAnalyzer] = {
            "mod": JarModAnalyzer("mod"),
            "mod_client": JarModAnalyzer("mod_client"),
        }

    def content_types(self) -> list[ContentType]:
        return list(CONTENT_TYPES)

    def content_analyzer(self, content_type: str) -> ContentAnalyzer:
        try:
            return self._analyzers[content_type]
        except KeyError:
            raise LookupError(f"unknown content type: {content_type!r}") from None

    def launch_spec(self, ctx: LaunchContext) -> LaunchSpec | None:
        return build_launch_spec(ctx)

    def console_codec(self) -> ConsoleCodec:
        return MinecraftConsoleCodec()

    def game_metadata(self, ctx: LaunchContext) -> dict | None:
        return detect_game_metadata(ctx.root_dir, ctx.provider_data)

    def config_schemas(self) -> list[ConfigSchema]:
        return [SERVER_PROPERTIES_SCHEMA]

    def config_codec(self, format: str) -> ConfigCodec:
        if format != "properties":
            raise LookupError(f"unknown config format: {format!r}")
        return PropertiesCodec()

    def backup_spec(self, root: Path) -> BackupSpec:
        return backup_spec(root)

    def quiesce_plan(self) -> QuiescePlan:
        return quiesce_plan()
