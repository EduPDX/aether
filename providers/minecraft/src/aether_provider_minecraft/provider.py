"""Minecraft provider implementation (content analysis + server launch)."""

from aether_sdk import (
    ConfigCodec,
    ConfigSchema,
    ConsoleCodec,
    ContentAnalyzer,
    ContentType,
    LaunchContext,
    LaunchSpec,
    ProviderManifest,
)

from aether_provider_minecraft.content.jar_analyzer import JarModAnalyzer
from aether_provider_minecraft.server.console import MinecraftConsoleCodec
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
        label="Mods",
        file_patterns=["*.jar", "*.jar.disabled"],
        default_directory="mods",
    ),
]


class MinecraftProvider:
    manifest = MANIFEST

    def __init__(self) -> None:
        self._analyzers: dict[str, ContentAnalyzer] = {"mod": JarModAnalyzer()}

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

    def config_schemas(self) -> list[ConfigSchema]:
        return [SERVER_PROPERTIES_SCHEMA]

    def config_codec(self, format: str) -> ConfigCodec:
        if format != "properties":
            raise LookupError(f"unknown config format: {format!r}")
        return PropertiesCodec()
