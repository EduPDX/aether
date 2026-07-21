"""Satisfactory provider (container SteamCMD; sem config em arquivo)."""

from pathlib import Path

from aether_sdk import (
    BackupSpec,
    ConfigSchema,
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

from aether_provider_satisfactory.catalog import catalog_entry
from aether_provider_satisfactory.server.backup import backup_spec, quiesce_plan
from aether_provider_satisfactory.server.console import SatisfactoryConsoleCodec
from aether_provider_satisfactory.server.container import (
    build_container_spec,
    provision,
    provision_schema,
)
from aether_provider_satisfactory.server.install import (
    install_disk_bytes,
    install_spec,
    installed_version,
    parse_versions,
    versions_spec,
)

MANIFEST = ProviderManifest(
    id="satisfactory",
    name="Satisfactory",
    version="0.1.0.dev0",
    games=["satisfactory"],
)


class SatisfactoryProvider:
    manifest = MANIFEST

    def catalog_entry(self) -> GameCatalogEntry:
        return catalog_entry()

    # Satisfactory não tem sistema de mods gerenciado pelo painel.
    def content_types(self) -> list[ContentType]:
        return []

    def content_analyzer(self, content_type: str) -> ContentAnalyzer:
        raise LookupError(f"unknown content type: {content_type!r}")

    # ------------------------------------------------------------- container --
    def container_spec(self, ctx: LaunchContext) -> ContainerSpec | None:
        return build_container_spec(ctx)

    def console_codec(self) -> ConsoleCodec:
        return SatisfactoryConsoleCodec()

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
        """Satisfactory não tem config a semear; só registra o build instalado
        e limpa qualquer pendência (que aqui é sempre vazia)."""
        return {
            "pending_config": {},
            "install": {"config_seeded": False, "build": installed_version(Path(root_dir))},
        }

    # ---------------------------------------------------------------- backup --
    def backup_spec(self, root: Path) -> BackupSpec:
        return backup_spec(root)

    def quiesce_plan(self) -> QuiescePlan:
        return quiesce_plan()
