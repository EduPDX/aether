"""Instance use cases."""

from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.application.ports import ContentFilesystem, InstanceRepository, ProviderRegistry
from aether_core.domain.errors import InstanceNotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance


class InstanceService:
    def __init__(
        self,
        repo: InstanceRepository,
        providers: ProviderRegistry,
        fs: ContentFilesystem,
        bus: EventBus,
    ) -> None:
        self._repo = repo
        self._providers = providers
        self._fs = fs
        self._bus = bus

    async def create(
        self,
        name: str,
        provider_id: str,
        root_dir: str,
        content_dirs: dict[str, str] | None = None,
        provider_data: dict | None = None,
    ) -> Instance:
        self._providers.get(provider_id)  # raises ProviderNotFoundError
        if not self._fs.is_dir(Path(root_dir)):
            raise ValidationFailedError(f"root_dir is not a directory: {root_dir}")
        instance = Instance.new(name, provider_id, root_dir, content_dirs, provider_data)
        await self._repo.add(instance)
        await self._bus.publish("instance.created", {"instance_id": instance.id, "name": name})
        return instance

    async def get(self, instance_id: str) -> Instance:
        instance = await self._repo.get(instance_id)
        if instance is None:
            raise InstanceNotFoundError(f"instance not found: {instance_id}")
        return instance

    async def list_all(self) -> list[Instance]:
        return await self._repo.list_all()

    async def delete(self, instance_id: str) -> None:
        """Deregister the instance. Never touches files on disk."""
        if not await self._repo.delete(instance_id):
            raise InstanceNotFoundError(f"instance not found: {instance_id}")
        await self._bus.publish("instance.deleted", {"instance_id": instance_id})
