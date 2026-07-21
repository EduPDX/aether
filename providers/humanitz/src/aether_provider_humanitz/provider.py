"""HumanitZ provider (container SteamCMD, config em GameServerSettings.ini)."""

from pathlib import Path

from aether_sdk import (
    BackupSpec,
    ConfigCodec,
    ConfigSchema,
    ConfigWarning,
    ConsoleCodec,
    ContainerSpec,
    ContentAnalyzer,
    ContentType,
    GameCatalogEntry,
    LaunchContext,
    ProviderManifest,
    QuiescePlan,
    VersionInfo,
)

from aether_provider_humanitz.catalog import catalog_entry
from aether_provider_humanitz.server.backup import backup_spec, quiesce_plan
from aether_provider_humanitz.server.console import HumanitZConsoleCodec
from aether_provider_humanitz.server.container import (
    build_container_spec,
    provision,
    provision_schema,
)
from aether_provider_humanitz.server.install import (
    install_disk_bytes,
    install_spec,
    installed_version,
    parse_versions,
    versions_spec,
)
from aether_provider_humanitz.server.serversettings import (
    SETTINGS_SCHEMA,
    GameServerIniCodec,
    config_warnings,
    seed,
)

MANIFEST = ProviderManifest(
    id="humanitz",
    name="HumanitZ",
    version="0.1.0.dev0",
    games=["humanitz"],
)


class HumanitZProvider:
    manifest = MANIFEST

    def catalog_entry(self) -> GameCatalogEntry:
        return catalog_entry()

    # HumanitZ não tem sistema de mods gerenciado pelo painel.
    def content_types(self) -> list[ContentType]:
        return []

    def content_analyzer(self, content_type: str) -> ContentAnalyzer:
        raise LookupError(f"unknown content type: {content_type!r}")

    # ------------------------------------------------------------- container --
    def container_spec(self, ctx: LaunchContext) -> ContainerSpec | None:
        return build_container_spec(ctx)

    def console_codec(self) -> ConsoleCodec:
        return HumanitZConsoleCodec()

    def provision_schema(self) -> ConfigSchema:
        return provision_schema()

    def provision(self, root_dir, values: dict) -> dict:
        return provision(Path(root_dir), values)

    # -------------------------------------------------------------- instalação --
    def install_spec(self, ctx: LaunchContext, version: str) -> ContainerSpec:
        return install_spec(ctx, version)

    def install_disk_bytes(self, version: str) -> int:
        return install_disk_bytes(version)

    def versions_spec(self) -> ContainerSpec:
        return versions_spec()

    def parse_versions(self, stdout: str) -> list[VersionInfo]:
        return parse_versions(stdout)

    def installed_version(self, root_dir) -> str:
        return installed_version(Path(root_dir))

    def after_install(self, root_dir, provider_data: dict) -> dict:
        """Prepara o GameServerSettings.ini com o jogo já em disco.

        Copia o arquivo de referência que a versão distribui e aplica o que o
        usuário escolheu na criação; numa atualização preserva o arquivo
        existente e não sobrescreve nada.
        """
        root = Path(root_dir)
        pendentes = dict(provider_data.get("pending_config") or {})
        criou = seed(root, pendentes)
        return {
            "pending_config": {},
            "install": {"config_seeded": criou, "build": installed_version(root)},
        }

    # ---------------------------------------------------------------- config --
    def config_schemas(self) -> list[ConfigSchema]:
        return [SETTINGS_SCHEMA]

    def config_codec(self, format: str) -> ConfigCodec:
        if format != "ini":
            raise LookupError(f"unknown config format: {format!r}")
        return GameServerIniCodec()

    def config_warnings(self, root: Path, values: dict) -> list[ConfigWarning]:
        return config_warnings(root, values)

    # ---------------------------------------------------------------- backup --
    def backup_spec(self, root: Path) -> BackupSpec:
        return backup_spec(root)

    def quiesce_plan(self) -> QuiescePlan:
        return quiesce_plan()
