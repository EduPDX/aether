"""Gerenciador de imagens: as imagens de container que os providers usam.

O pull roda como task em segundo plano e o progresso sai pelo event bus
(``images.pull``): baixar uma imagem de servidor leva minutos e prender uma
request HTTP nisso derrubaria o pull junto com qualquer refresh da página.
"""

import asyncio
import contextlib
import logging

from aether_sdk import LaunchContext, SupportsContainer

from aether_core.application.events import EventBus
from aether_core.application.ports import ContainerRuntime, ImageInfo, ProviderRegistry
from aether_core.domain.errors import ConflictError, ValidationFailedError

log = logging.getLogger(__name__)


class ImageService:
    def __init__(
        self, runtime: ContainerRuntime, providers: ProviderRegistry, bus: EventBus
    ) -> None:
        self._runtime = runtime
        self._providers = providers
        self._bus = bus
        self._pulls: dict[str, asyncio.Task] = {}

    def referenced_images(self) -> list[dict]:
        """Imagens que os providers declaram, sem exigir instância criada.

        Usa um ``LaunchContext`` vazio: o spec pode falhar para providers que
        exigem provision antes — nesse caso o provider simplesmente não lista
        imagem aqui, o que é honesto.
        """
        refs = []
        for pid, provider in self._providers.all().items():
            if not isinstance(provider, SupportsContainer):
                continue
            with contextlib.suppress(Exception):
                spec = provider.container_spec(LaunchContext(root_dir=".", provider_data={}))
                if spec is not None:
                    refs.append({"provider_id": pid, "image": spec.image})
        return refs

    async def list_installed(self) -> list[ImageInfo]:
        await self._runtime.ensure_available()
        return await self._runtime.list_images()

    async def start_pull(self, ref: str) -> None:
        ref = ref.strip()
        if not ref or any(c.isspace() for c in ref):
            raise ValidationFailedError(f"invalid image reference: {ref!r}")
        await self._runtime.ensure_available()
        if ref in self._pulls and not self._pulls[ref].done():
            raise ConflictError(f"pull of {ref} is already in progress")
        self._pulls[ref] = asyncio.create_task(self._pull(ref))

    def pulling(self) -> list[str]:
        return [ref for ref, task in self._pulls.items() if not task.done()]

    async def remove(self, ref: str) -> None:
        await self._runtime.ensure_available()
        try:
            await self._runtime.remove_image(ref)
        except Exception as exc:  # noqa: BLE001 - imagem em uso, tag inexistente...
            raise ValidationFailedError(f"could not remove image: {exc}") from exc

    async def shutdown(self) -> None:
        for task in self._pulls.values():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _pull(self, ref: str) -> None:
        await self._bus.publish("images.pull", {"image": ref, "status": "started"})
        try:
            async for event in self._runtime.pull_image(ref):
                # Repassa o evento da engine como veio: a UI mostra progresso
                # por camada sem o Core inventar um formato próprio.
                await self._bus.publish(
                    "images.pull", {"image": ref, "status": "progress", "detail": event}
                )
            await self._bus.publish("images.pull", {"image": ref, "status": "done"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("pull da imagem %s falhou: %s", ref, exc)
            await self._bus.publish(
                "images.pull", {"image": ref, "status": "error", "error": str(exc)}
            )
