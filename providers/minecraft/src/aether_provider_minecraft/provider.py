"""Minecraft provider implementation (content analysis + server launch)."""

from pathlib import Path

from aether_sdk import (
    BackupSpec,
    ConfigCodec,
    ConfigSchema,
    ConsoleCodec,
    ContainerSpec,
    ContentAnalyzer,
    ContentSource,
    ContentType,
    GameCatalogEntry,
    IconSpec,
    LaunchContext,
    LaunchSpec,
    ProviderManifest,
    QuiescePlan,
)

from aether_provider_minecraft.catalog import catalog_entry
from aether_provider_minecraft.content.jar_analyzer import JarModAnalyzer
from aether_provider_minecraft.content.modrinth import ModrinthSource
from aether_provider_minecraft.server.backup import backup_spec, quiesce_plan
from aether_provider_minecraft.server.console import MinecraftConsoleCodec
from aether_provider_minecraft.server.container import (
    PROVISION_SCHEMA,
    build_container_spec,
    provision,
)
from aether_provider_minecraft.server.game_meta import catalog_context, detect_game_metadata
from aether_provider_minecraft.server.launch import build_launch_spec
from aether_provider_minecraft.server.players import (
    apply_player_action,
    player_command,
    player_lists,
    player_live_plan,
)
from aether_provider_minecraft.server.properties import (
    SERVER_PROPERTIES_SCHEMA,
    PropertiesCodec,
    config_warnings,
)
from aether_provider_minecraft.server.versions import (
    current_version,
    fetch_versions,
    is_modded,
    pin_version,
)

MANIFEST = ProviderManifest(
    id="minecraft",
    name="Minecraft",
    version="0.1.0.dev0",
    games=["minecraft-java"],
    # O jogo exige exatamente um PNG 64x64 chamado server-icon.png; qualquer
    # outra coisa e o servidor ignora o arquivo em silêncio.
    icon_spec=IconSpec(file="server-icon.png", size=64),
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
        self._http = None
        self._http_post = None
        self._versoes_cache: tuple[list, float] | None = None
        self._analyzers: dict[str, ContentAnalyzer] = {
            "mod": JarModAnalyzer("mod"),
            "mod_client": JarModAnalyzer("mod_client"),
        }

    def catalog_entry(self) -> GameCatalogEntry:
        return catalog_entry()

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

    def container_spec(self, ctx: LaunchContext) -> ContainerSpec | None:
        return build_container_spec(ctx)

    def provision_schema(self) -> ConfigSchema:
        return PROVISION_SCHEMA

    def provision(self, root_dir, values: dict) -> dict:
        return provision(root_dir, values)

    def game_metadata(self, ctx: LaunchContext) -> dict | None:
        return detect_game_metadata(ctx.root_dir, ctx.provider_data)

    def catalog_context(self, provider_data: dict) -> tuple[str | None, str | None]:
        """Versão e loader para o Core filtrar o catálogo — vê `catalog_context`."""
        return catalog_context(provider_data)

    def config_schemas(self) -> list[ConfigSchema]:
        return [SERVER_PROPERTIES_SCHEMA]

    def config_codec(self, format: str) -> ConfigCodec:
        if format != "properties":
            raise LookupError(f"unknown config format: {format!r}")
        return PropertiesCodec()

    def content_sources(self) -> list[ContentSource]:
        """Catálogos disponíveis para Minecraft.

        Só existem quando o Core injeta um transporte HTTP — o provider não
        abre conexão por conta própria, para continuar testável sem rede.
        """
        if self._http is None:
            return []
        return [ModrinthSource(self._http, self._http_post)]

    def set_http(self, get, post=None) -> None:
        self._http = get
        self._http_post = post

    def config_warnings(self, root: Path, values: dict) -> list:
        return config_warnings(root, values)

    def backup_spec(self, root: Path) -> BackupSpec:
        return backup_spec(root)

    def quiesce_plan(self) -> QuiescePlan:
        return quiesce_plan()

    # ------------------------------------------------------------ jogadores --
    def player_lists(self, root: Path) -> list:
        return player_lists(root)

    def player_command(self, action, name: str, reason: str = "") -> str | None:
        return player_command(action, name, reason)

    def apply_player_action(self, root: Path, action, name: str, reason: str = "") -> None:
        apply_player_action(root, action, name, reason)

    def player_live_plan(self, root: Path, action) -> str | None:
        """Servidor no ar: aplicar pelo arquivo? Veja `player_live_plan`."""
        return player_live_plan(root, action)

    # -------------------------------------------------------------- versões --
    # Capacidade própria (não SupportsInstall): a versão é a env VERSION do
    # container itzg, trocada editando o provider_data e recriando o container.
    async def game_versions(self) -> list:
        """Versões do Minecraft, do manifesto oficial da Mojang.

        Cacheado em memória: o manifesto muda poucas vezes por semana e a
        consulta custa uma ida à rede — sem cache, cada abertura da aba Versão
        esperaria por ela.
        """
        import time

        agora = time.monotonic()
        if self._versoes_cache is not None:
            versoes, quando = self._versoes_cache
            if agora - quando < 1800:  # 30 min
                return versoes
        versoes = await fetch_versions(self._http)
        if versoes:  # não cacheia falha de rede: da próxima tenta de novo
            self._versoes_cache = (versoes, agora)
        return versoes

    def current_game_version(self, provider_data: dict) -> str:
        return current_version(provider_data)

    def game_version_is_modded(self, provider_data: dict) -> bool:
        return is_modded(provider_data)

    def pin_game_version(self, provider_data: dict, version: str) -> dict:
        return pin_version(provider_data, version)
