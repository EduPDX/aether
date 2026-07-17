"""Minecraft provider implementation (contract v0: content analysis)."""

from aether_sdk import ContentAnalyzer, ContentType, ProviderManifest

from aether_provider_minecraft.content.jar_analyzer import JarModAnalyzer

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
