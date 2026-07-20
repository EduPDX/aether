"""7 Days to Die provider (containers, config XML, mods por pasta)."""

from pathlib import Path

from aether_sdk import (
    BackupSpec,
    ConfigCodec,
    ConfigSchema,
    ConsoleCodec,
    ContainerSpec,
    ContentAnalyzer,
    ContentType,
    LaunchContext,
    ProviderManifest,
    QuiescePlan,
    VersionInfo,
)

from aether_provider_sevendays.content.modinfo_analyzer import ModInfoAnalyzer
from aether_provider_sevendays.server.backup import backup_spec, quiesce_plan
from aether_provider_sevendays.server.console import SevenDaysConsoleCodec
from aether_provider_sevendays.server.container import (
    build_container_spec,
    provision,
    provision_schema,
)
from aether_provider_sevendays.server.install import (
    install_spec,
    installed_version,
    parse_versions,
    versions_spec,
)
from aether_provider_sevendays.server.serverconfig import (
    SERVERCONFIG_SCHEMA,
    ServerConfigXmlCodec,
    config_warnings,
    seed,
)

MANIFEST = ProviderManifest(
    id="sevendays",
    name="7 Days to Die",
    version="0.1.0.dev0",
    games=["seven-days-to-die"],
)

CONTENT_TYPES = [
    ContentType(
        id="mod",
        label="Mods",
        # Mods são pastas (ou zips ainda não extraídos) dentro de Mods/.
        file_patterns=["*"],
        default_directory="server/Mods",
    ),
]


class SevenDaysProvider:
    manifest = MANIFEST

    def __init__(self) -> None:
        self._analyzers: dict[str, ContentAnalyzer] = {"mod": ModInfoAnalyzer("mod")}

    def content_types(self) -> list[ContentType]:
        return list(CONTENT_TYPES)

    def content_analyzer(self, content_type: str) -> ContentAnalyzer:
        try:
            return self._analyzers[content_type]
        except KeyError:
            raise LookupError(f"unknown content type: {content_type!r}") from None

    # ------------------------------------------------------------- container --
    def container_spec(self, ctx: LaunchContext) -> ContainerSpec | None:
        return build_container_spec(ctx)

    def console_codec(self) -> ConsoleCodec:
        return SevenDaysConsoleCodec()

    def provision_schema(self) -> ConfigSchema:
        return provision_schema()

    def provision(self, root_dir, values: dict) -> dict:
        return provision(Path(root_dir), values)

    # -------------------------------------------------------------- instalação --
    def install_spec(self, ctx: LaunchContext, version: str) -> ContainerSpec:
        return install_spec(ctx, version)

    def versions_spec(self) -> ContainerSpec:
        return versions_spec()

    def parse_versions(self, stdout: str) -> list[VersionInfo]:
        return parse_versions(stdout)

    def installed_version(self, root_dir) -> str:
        return installed_version(Path(root_dir))

    def after_install(self, root_dir, provider_data: dict) -> dict:
        """Prepara o serverconfig.xml com o jogo já em disco.

        Na primeira instalação parte do arquivo distribuído pela versão (com
        as ~69 propriedades documentadas) e aplica o que o usuário escolheu na
        criação; numa atualização preserva o arquivo e acrescenta só o que a
        versão nova trouxe.
        """
        root = Path(root_dir)
        pendentes = dict(provider_data.get("pending_config") or {})
        criou, novas = seed(root, pendentes)
        return {
            "pending_config": {},
            "install": {
                "config_seeded": criou,
                "new_properties": novas,
                "build": installed_version(root),
            },
        }

    # ---------------------------------------------------------------- config --
    def config_schemas(self) -> list[ConfigSchema]:
        return [SERVERCONFIG_SCHEMA]

    def config_codec(self, format: str) -> ConfigCodec:
        if format != "xml":
            raise LookupError(f"unknown config format: {format!r}")
        return ServerConfigXmlCodec()

    def config_warnings(self, root: Path, values: dict) -> list:
        return config_warnings(root, values)

    # ---------------------------------------------------------------- backup --
    def backup_spec(self, root: Path) -> BackupSpec:
        return backup_spec(root)

    def quiesce_plan(self) -> QuiescePlan:
        return quiesce_plan()
