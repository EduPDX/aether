"""Instance use cases."""

import asyncio
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path

from aether_sdk import SupportsContainer, SupportsProvision

from aether_core.application.events import EventBus
from aether_core.application.ports import ContentFilesystem, InstanceRepository, ProviderRegistry
from aether_core.domain.errors import InstanceNotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance, InstanceRuntime


class InstanceService:
    def __init__(
        self,
        repo: InstanceRepository,
        providers: ProviderRegistry,
        fs: ContentFilesystem,
        bus: EventBus,
        instances_dir: Path | None = None,
    ) -> None:
        self._repo = repo
        self._providers = providers
        self._fs = fs
        self._bus = bus
        self._instances_dir = instances_dir

    async def create(
        self,
        name: str,
        provider_id: str,
        root_dir: str = "",
        runtime: str = InstanceRuntime.PROCESS,
        content_dirs: dict[str, str] | None = None,
        provider_data: dict | None = None,
        provision_values: dict | None = None,
    ) -> Instance:
        provider = self._providers.get(provider_id)  # raises ProviderNotFoundError
        if runtime not in (InstanceRuntime.PROCESS, InstanceRuntime.DOCKER):
            raise ValidationFailedError(f"unknown runtime: {runtime}")
        if runtime == InstanceRuntime.DOCKER and not isinstance(provider, SupportsContainer):
            raise ValidationFailedError(f"provider {provider_id!r} does not support containers")

        provisioned_dir: Path | None = None
        if provision_values is not None:
            # Criação do zero: o Core dá um diretório vazio gerenciado e o
            # provider materializa os arquivos iniciais a partir do formulário.
            if not isinstance(provider, SupportsProvision):
                raise ValidationFailedError(
                    f"provider {provider_id!r} does not support server creation"
                )
            if self._instances_dir is None:
                raise ValidationFailedError("managed instances directory is not configured")
            provisioned_dir = self._instances_dir / uuid.uuid4().hex
            provisioned_dir.mkdir(parents=True, exist_ok=False)
            try:
                data = await asyncio.to_thread(
                    provider.provision, provisioned_dir, dict(provision_values)
                )
            except ValidationFailedError:
                shutil.rmtree(provisioned_dir, ignore_errors=True)
                raise
            except Exception as exc:  # noqa: BLE001 - provision de provider não derruba a API
                shutil.rmtree(provisioned_dir, ignore_errors=True)
                raise ValidationFailedError(f"provider provisioning failed: {exc}") from exc
            root_dir = str(provisioned_dir)
            provider_data = {**(provider_data or {}), **(data or {})}

        if not root_dir or not self._fs.is_dir(Path(root_dir)):
            raise ValidationFailedError(f"root_dir is not a directory: {root_dir}")
        instance = Instance.new(name, provider_id, root_dir, runtime, content_dirs, provider_data)
        await self._repo.add(instance)
        await self._bus.publish("instance.created", {"instance_id": instance.id, "name": name})
        return instance

    async def merge_provider_data(self, instance_id: str, mudancas: dict) -> Instance:
        """Mescla mudanças no provider_data (o que a instalação descobriu, por
        exemplo). Merge raso de propósito: o provider é dono das suas chaves e
        substitui o bloco inteiro quando quer."""
        instance = await self.get(instance_id)
        novo = {**instance.provider_data, **mudancas}
        await self._repo.update_provider_data(instance_id, novo)
        return await self.get(instance_id)

    async def get(self, instance_id: str) -> Instance:
        instance = await self._repo.get(instance_id)
        if instance is None:
            raise InstanceNotFoundError(f"instance not found: {instance_id}")
        return instance

    async def list_all(self) -> list[Instance]:
        return await self._repo.list_all()

    async def delete(self, instance_id: str, *, remover=None, apagar_dados: bool = True) -> dict:
        """Remove a instância e o que era exclusivo dela.

        Pasta adotada nunca é apagada — o servidor é do usuário e existia antes
        do painel. Já o que o Core criou (pasta gerenciada, container, backups)
        sai junto: deixar para trás foi o que encheu 17 GB de disco com pastas
        de instâncias que ninguém mais via.

        A remoção dos arquivos vem antes de apagar o registro: se o processo
        morrer no meio, sobra uma instância órfã visível na interface (que o
        usuário pode remover de novo) em vez de arquivos invisíveis para sempre.
        """
        instance = await self.get(instance_id)

        relatorio = {}
        if remover is not None:
            rel = await remover.remove(instance, apagar_dados=apagar_dados)
            relatorio = asdict(rel)

        relatorio["registros_removidos"] = await self._repo.delete_related(instance_id)
        if not await self._repo.delete(instance_id):
            raise InstanceNotFoundError(f"instance not found: {instance_id}")
        await self._bus.publish("instance.deleted", {"instance_id": instance_id})
        return relatorio
