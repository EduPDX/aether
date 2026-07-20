"""Lixeira: guardar, listar, restaurar e apagar de vez.

Um único serviço é dono da pasta de lixeira. Antes disto dois lugares moviam
arquivos para lá por conta própria — o explorador e a tela de conteúdo — cada
um com sua regra de colisão, e nenhum dos dois anotava de onde o arquivo tinha
saído. O resultado era uma pasta que só crescia e da qual nada voltava.
"""

import asyncio
import shutil
import uuid
from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.domain.errors import ConflictError, ForbiddenError, NotFoundError
from aether_core.domain.instances import Instance
from aether_core.domain.trash import (
    TrashItem,
    TrashOrigin,
    select_for_pruning,
    stored_name_for,
)


def directory_size(path: Path) -> int:
    """Soma dos arquivos, ignorando o que não dá para medir.

    Links quebrados e arquivos que somem no meio da varredura não podem
    derrubar a operação: o tamanho é informativo, não é o objetivo.
    """
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


class TrashService:
    def __init__(self, trash_root: Path, repo, bus: EventBus) -> None:
        self._root = trash_root
        self._repo = repo
        self._bus = bus

    def _dir(self, instance_id: str) -> Path:
        return self._root / instance_id

    def _stored(self, item: TrashItem) -> Path:
        return self._dir(item.instance_id) / item.stored_name

    # ------------------------------------------------------------- guardar --
    async def store(
        self,
        instance: Instance,
        source: Path,
        original_path: str,
        *,
        origin: TrashOrigin = TrashOrigin.FILES,
        content_type: str = "",
    ) -> TrashItem:
        """Move `source` para a lixeira, anotando de onde saiu."""
        if not source.exists():
            raise NotFoundError(f"not found: {original_path}")

        is_dir = source.is_dir()
        pasta = self._dir(instance.id)
        stored = stored_name_for(source.name, uuid.uuid4().hex)

        def _mover() -> int:
            pasta.mkdir(parents=True, exist_ok=True)
            tamanho = directory_size(source)
            shutil.move(str(source), str(pasta / stored))
            return tamanho

        size = await asyncio.to_thread(_mover)

        item = TrashItem.new(
            instance.id,
            original_path.replace("\\", "/").lstrip("/"),
            stored,
            is_dir=is_dir,
            size_bytes=size,
            origin=origin,
            content_type=content_type,
        )
        await self._repo.add(item)
        await self._bus.publish(
            "trash.stored", {"instance_id": instance.id, "path": item.original_path}
        )
        return item

    # -------------------------------------------------------------- listar --
    async def list(self, instance: Instance) -> list[TrashItem]:
        """Itens da lixeira, descartando os que sumiram do disco.

        Alguém pode ter limpado a pasta por fora — por SSH, por exemplo. Uma
        linha sem arquivo correspondente só serviria para oferecer um
        "restaurar" que falha, então some da lista e do banco.
        """
        itens = await self._repo.list_for(instance.id)
        vivos = []
        for item in itens:
            if self._stored(item).exists():
                vivos.append(item)
            else:
                await self._repo.delete(item.id)
        return vivos

    # ----------------------------------------------------------- restaurar --
    async def restore(self, instance: Instance, item_id: str) -> str:
        item = await self._require(instance, item_id)
        stored = self._stored(item)

        root = Path(instance.root_dir).resolve()
        destino = (root / item.original_path).resolve()
        # A origem veio do banco, mas o banco não é sagrado: se a linha for
        # adulterada, restaurar não pode virar escrita fora da instância.
        if destino != root and root not in destino.parents:
            raise ForbiddenError("stored path escapes the instance directory")
        if destino.exists():
            raise ConflictError(f"already exists: {item.original_path}")

        def _voltar() -> None:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stored), str(destino))

        await asyncio.to_thread(_voltar)
        await self._repo.delete(item.id)
        await self._bus.publish(
            "trash.restored", {"instance_id": instance.id, "path": item.original_path}
        )
        return item.original_path

    # -------------------------------------------------- apagar de vez/limpar --
    async def purge(self, instance: Instance, item_id: str) -> None:
        item = await self._require(instance, item_id)
        await asyncio.to_thread(self._remover, self._stored(item))
        await self._repo.delete(item.id)
        await self._bus.publish(
            "trash.purged", {"instance_id": instance.id, "path": item.original_path}
        )

    async def empty(self, instance: Instance) -> int:
        itens = await self.list(instance)
        for item in itens:
            await asyncio.to_thread(self._remover, self._stored(item))
            await self._repo.delete(item.id)
        if itens:
            await self._bus.publish(
                "trash.emptied", {"instance_id": instance.id, "count": len(itens)}
            )
        return len(itens)

    async def prune(self, instance: Instance, now) -> int:
        """Limpeza automática por idade e por espaço."""
        alvos = select_for_pruning(await self.list(instance), now)
        for item in alvos:
            await asyncio.to_thread(self._remover, self._stored(item))
            await self._repo.delete(item.id)
        return len(alvos)

    # ------------------------------------------------------------ internos --
    async def _require(self, instance: Instance, item_id: str) -> TrashItem:
        item = await self._repo.get(item_id)
        # Conferir o dono evita que o id de uma instância sirva para mexer na
        # lixeira de outra.
        if item is None or item.instance_id != instance.id:
            raise NotFoundError(f"trash item not found: {item_id}")
        if not self._stored(item).exists():
            await self._repo.delete(item.id)
            raise NotFoundError(f"trash item is gone from disk: {item_id}")
        return item

    @staticmethod
    def _remover(path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
