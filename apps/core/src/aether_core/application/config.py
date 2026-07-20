"""Schema-driven configuration use cases."""

from pathlib import Path

from aether_sdk import SupportsConfig

from aether_core.application.events import EventBus
from aether_core.application.files import FilesService
from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import NotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance


class ConfigService:
    def __init__(self, providers: ProviderRegistry, files: FilesService, bus: EventBus) -> None:
        self._providers = providers
        self._files = files
        self._bus = bus

    def _provider(self, instance: Instance) -> SupportsConfig | None:
        provider = self._providers.get(instance.provider_id)
        return provider if isinstance(provider, SupportsConfig) else None

    async def list_configs(self, instance: Instance) -> list[dict]:
        provider = self._provider(instance)
        if provider is None:
            return []
        out = []
        for schema in provider.config_schemas():
            codec = provider.config_codec(schema.format)
            try:
                text = await self._files.read_text(instance, schema.file)
                values = codec.parse(text)
                exists = True
            except NotFoundError:
                values = {}
                exists = False
            avisos = []
            emitir = getattr(provider, "config_warnings", None)
            if callable(emitir):
                try:
                    avisos = [
                        {"key": a.key, "message": a.message, "level": a.level}
                        for a in emitir(Path(instance.root_dir), values)
                    ]
                except Exception:
                    # Um aviso quebrado não pode impedir a tela de config de abrir.
                    avisos = []
            visivel = schema
            if schema.fields_from_file and exists:
                # A versão instalada é que decide o que existe: oferecer um
                # campo que aquele build ignora produz configuração fantasma —
                # o usuário salva, nada acontece, e não há como saber por quê.
                visivel = schema.model_copy(deep=True)
                visivel.fields = [f for f in schema.fields if f.key in values]

            out.append(
                {
                    "schema": visivel.model_dump(),
                    "values": values,
                    "file_exists": exists,
                    "warnings": avisos,
                }
            )
        return out

    async def update_config(
        self, instance: Instance, schema_id: str, values: dict[str, str]
    ) -> None:
        provider = self._provider(instance)
        if provider is None:
            raise ValidationFailedError(f"provider {instance.provider_id!r} has no config schemas")
        schema = next((s for s in provider.config_schemas() if s.id == schema_id), None)
        if schema is None:
            raise NotFoundError(f"unknown config schema: {schema_id}")

        known_keys = {f.key for f in schema.fields}
        unknown = set(values) - known_keys
        if unknown:
            raise ValidationFailedError(f"unknown config keys: {sorted(unknown)}")

        codec = provider.config_codec(schema.format)
        try:
            text = await self._files.read_text(instance, schema.file)
        except NotFoundError:
            text = ""

        if schema.fields_from_file and text:
            # Salvar não pode inventar propriedade: numa versão que não conhece
            # a chave, escrevê-la só suja o arquivo sem configurar nada.
            no_arquivo = set(codec.parse(text))
            ignoradas = sorted(set(values) - no_arquivo)
            if ignoradas:
                raise ValidationFailedError(
                    "estas opções não existem na versão instalada do servidor: "
                    + ", ".join(ignoradas)
                )
        new_text = codec.apply(text, {k: str(v) for k, v in values.items()})
        await self._files.write_text(instance, schema.file, new_text)
        await self._bus.publish("config.updated", {"instance_id": instance.id, "schema": schema_id})
