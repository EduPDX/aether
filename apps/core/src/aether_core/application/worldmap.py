"""Mapa-mundi: liga/desliga o sidecar de mapa de uma instância.

O provider descreve o *quê* (:class:`aether_sdk.MapPlan` — imagem, volumes,
porta, config a semear); este serviço faz o *como*: grava a config, garante a
imagem, cria e sobe o container à parte pela camada de runtime que já roda o
jogo, e guarda o estado no ``provider_data`` da instância. Ver ADR 0001.

O container do mapa é deliberadamente **separado** do container do jogo: nome
próprio ``aether-map-{id}`` e label próprio (:data:`MAP_LABEL`), nunca o
``aether.instance`` — assim o reconcile que readota o servidor do jogo no
restart do Core não confunde um pelo outro.
"""

import logging
from pathlib import Path
from typing import Protocol

from aether_sdk import LaunchContext, MapPlan, SupportsMap

from aether_core.application.events import EventBus
from aether_core.application.ports import InstanceRepository, ProviderRegistry
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.instances import Instance

log = logging.getLogger(__name__)

MAP_LABEL = "aether.map"
"""Marca o container do mapa com o id da instância dona.

Distinto de ``aether.instance`` de propósito: a varredura que readota/limpa os
containers *do jogo* filtra por aquele label e por isso ignora o do mapa — os
dois ciclos de vida não se cruzam.
"""


class MapRuntime(Protocol):
    """Subconjunto de ``ContainerRuntime`` que o mapa precisa."""

    async def ensure_available(self) -> None: ...

    async def has_image(self, ref: str) -> bool: ...

    def pull_image(self, ref: str): ...

    async def create(self, name: str, labels: dict, spec, root_dir: Path) -> str: ...

    async def start(self, container_id: str) -> None: ...

    async def remove(self, container_id: str) -> None: ...


class MapService:
    def __init__(
        self,
        providers: ProviderRegistry,
        repo: InstanceRepository,
        runtime: MapRuntime,
        bus: EventBus,
    ) -> None:
        self._providers = providers
        self._repo = repo
        self._runtime = runtime
        self._bus = bus

    @staticmethod
    def container_name(instance_id: str) -> str:
        return f"aether-map-{instance_id}"

    # ------------------------------------------------------------- consultas --
    def status(self, instance: Instance) -> dict:
        """Estado guardado do mapa; ``enabled=False`` quando nunca foi ligado."""
        estado = dict(instance.provider_data.get("map") or {})
        estado.setdefault("enabled", False)
        estado["supported"] = isinstance(self._providers.get(instance.provider_id), SupportsMap)
        return estado

    # ------------------------------------------------------------ casos de uso --
    async def enable(self, instance: Instance) -> dict:
        """Sobe o sidecar de mapa e devolve o estado (porta/caminho).

        A URL final é montada pelo cliente a partir do endereço do servidor que
        ele já conhece + esta porta — o Core não presume o próprio endereço
        público (mesma razão pela qual isso fica fora daqui).
        """
        plan = self._plan_or_raise(instance)
        root = Path(instance.root_dir)

        # Semeia a config e garante as pastas dos volumes graváveis antes do
        # boot: o BlueMap gera o resto (webserver/webapp/maps) por cima.
        self._prepare_files(root, plan)

        await self._runtime.ensure_available()
        await self._ensure_image(instance, plan.container.image)

        name = self.container_name(instance.id)
        container_id = await self._runtime.create(
            name=name,
            labels={MAP_LABEL: instance.id},
            spec=plan.container,
            root_dir=root,
        )
        await self._runtime.start(container_id)

        estado = {"enabled": True, "port": plan.web_port, "path": plan.url_path}
        await self._save(instance, estado)
        await self._bus.publish("map.enabled", {"instance_id": instance.id, **estado})
        log.info("mapa ligado para a instância %s (porta %s)", instance.id, plan.web_port)
        return {**estado, "supported": True}

    async def disable(self, instance: Instance) -> dict:
        """Derruba o sidecar de mapa; os tiles já renderizados ficam no volume."""
        with _ignore("remover container do mapa"):
            await self._runtime.remove(self.container_name(instance.id))
        estado = {"enabled": False}
        await self._save(instance, estado)
        await self._bus.publish("map.disabled", {"instance_id": instance.id})
        log.info("mapa desligado para a instância %s", instance.id)
        return {**estado, "supported": True}

    # -------------------------------------------------------------- internos --
    def _plan_or_raise(self, instance: Instance) -> MapPlan:
        provider = self._providers.get(instance.provider_id)
        if not isinstance(provider, SupportsMap):
            raise ValidationFailedError(
                f"o provider {instance.provider_id!r} não oferece mapa-mundi"
            )
        ctx = LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data)
        plan = provider.map_plan(ctx)
        if plan is None:
            raise ValidationFailedError(
                "o mundo ainda não foi gerado — inicie o servidor ao menos uma "
                "vez antes de ativar o mapa"
            )
        return plan

    @staticmethod
    def _prepare_files(root: Path, plan: MapPlan) -> None:
        # Pastas dos volumes graváveis (o mundo só-leitura já existe).
        for vol in plan.container.volumes:
            if not vol.read_only:
                (root / vol.subdir).mkdir(parents=True, exist_ok=True)
        # Config semeada — respeita ``keep_existing`` para não desfazer ajuste
        # manual do dono num segundo "Ativar mapa".
        for seed in plan.seed_files:
            destino = root / seed.path
            if seed.keep_existing and destino.exists():
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(seed.content, encoding="utf-8")

    async def _ensure_image(self, instance: Instance, image: str) -> None:
        if await self._runtime.has_image(image):
            return
        await self._bus.publish("map.pulling", {"instance_id": instance.id, "image": image})
        async for _ in self._runtime.pull_image(image):
            pass

    async def _save(self, instance: Instance, estado: dict) -> None:
        # `Instance` é frozen — não dá (nem precisa) mutar em memória: o estado
        # persiste no banco e a próxima leitura carrega a instância já atualizada.
        novo = {**instance.provider_data, "map": estado}
        await self._repo.update_provider_data(instance.id, novo)


class _ignore:
    """Suprime falha de limpeza — desligar não pode falhar por um container
    que já não existe."""

    def __init__(self, o_que: str) -> None:
        self._o_que = o_que

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            log.warning("falha ao %s (ignorada): %s", self._o_que, exc)
        return True
