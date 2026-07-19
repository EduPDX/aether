"""Content use cases: list, toggle, trash, copy and compare instance content.

Analysis is delegated to the instance's provider (``ContentAnalyzer``);
results are cached by file identity (path + size + mtime) so re-listing
hundreds of mods is instant.
"""

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

from aether_sdk import ContentAnalyzer, ContentMetadata, ContentType

from aether_core.application.events import EventBus
from aether_core.application.ports import (
    CachedContent,
    ContentCache,
    ContentFilesystem,
    FileEntry,
    IconStore,
    ProviderRegistry,
)
from aether_core.domain.content import ContentItem, is_enabled, mark_duplicates, toggled_name
from aether_core.domain.errors import (
    ContentFolderMissingError,
    ContentTypeNotFoundError,
    ValidationFailedError,
)
from aether_core.domain.instances import Instance


@dataclass
class CompareResult:
    only_in_a: list[ContentItem]
    only_in_b: list[ContentItem]
    version_diffs: list[dict]


def _cache_key(folder: Path, entry: FileEntry) -> str:
    raw = f"{folder / entry.name}|{entry.size}|{entry.mtime}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()


class ContentService:
    def __init__(
        self,
        providers: ProviderRegistry,
        fs: ContentFilesystem,
        cache: ContentCache,
        icons: IconStore,
        trash_root: Path,
        bus: EventBus,
    ) -> None:
        self._providers = providers
        self._fs = fs
        self._cache = cache
        self._icons = icons
        self._trash_root = trash_root
        self._bus = bus

    # ------------------------------------------------------------- helpers --
    def _content_type(self, instance: Instance, ctype_id: str) -> ContentType:
        provider = self._providers.get(instance.provider_id)
        for ct in provider.content_types():
            if ct.id == ctype_id:
                return ct
        raise ContentTypeNotFoundError(
            f"provider {instance.provider_id!r} has no content type {ctype_id!r}"
        )

    def folder_for(self, instance: Instance, ctype_id: str) -> Path:
        """Pasta de um tipo de conteúdo pelo id — usada pelo catálogo."""
        return self._folder(instance, self._content_type(instance, ctype_id))

    def _folder(self, instance: Instance, ct: ContentType) -> Path:
        """Pasta do tipo de conteúdo; criada sob demanda.

        Tipos gerenciados (ex.: o perfil de cliente) não existem numa
        instalação nova — criar na primeira visita evita erro confuso.
        """
        folder = instance.resolve_content_dir(ct)
        if not self._fs.is_dir(folder):
            root = Path(instance.root_dir)
            if not self._fs.is_dir(root):
                raise ContentFolderMissingError(f"instance root does not exist: {root}")
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    # ------------------------------------------------------------ use cases --
    async def list_content(self, instance: Instance, ctype_id: str) -> list[ContentItem]:
        ct = self._content_type(instance, ctype_id)
        provider = self._providers.get(instance.provider_id)
        analyzer = provider.content_analyzer(ct.id)
        folder = self._folder(instance, ct)

        entries = await asyncio.to_thread(self._fs.scan, folder, ct.file_patterns)
        keys = {entry.name: _cache_key(folder, entry) for entry in entries}
        cached = await self._cache.get_many(list(keys.values()))

        missing = [e for e in entries if keys[e.name] not in cached]
        if missing:
            analyzed = await asyncio.to_thread(self._analyze_batch, analyzer, folder, missing)
            await self._cache.put_many({keys[name]: cc for name, cc in analyzed.items()})
            cached.update({keys[name]: cc for name, cc in analyzed.items()})

        items: list[ContentItem] = []
        for entry in entries:
            cc = cached[keys[entry.name]]
            items.append(
                ContentItem(
                    file=entry.name,
                    enabled=is_enabled(entry.name),
                    size_bytes=entry.size,
                    mtime=entry.mtime,
                    metadata=ContentMetadata(**cc.metadata),
                    icon_file=cc.icon_file,
                )
            )
        mark_duplicates(items)
        return items

    def _analyze_batch(
        self, analyzer: ContentAnalyzer, folder: Path, entries: list[FileEntry]
    ) -> dict[str, CachedContent]:
        out: dict[str, CachedContent] = {}
        for entry in entries:
            meta = analyzer.analyze(folder / entry.name)
            icon_file = self._icons.save(meta.icon_png) if meta.icon_png else None
            out[entry.name] = CachedContent(
                metadata=meta.model_dump(mode="json", exclude={"icon_png"}),
                icon_file=icon_file,
            )
        return out

    async def toggle(self, instance: Instance, ctype_id: str, file_name: str) -> str:
        ct = self._content_type(instance, ctype_id)
        folder = self._folder(instance, ct)
        file_name = Path(file_name).name  # no path traversal
        new_name = toggled_name(file_name)
        await asyncio.to_thread(self._fs.rename, folder, file_name, new_name)
        await self._bus.publish(
            "content.toggled",
            {"instance_id": instance.id, "file": file_name, "new_file": new_name},
        )
        return new_name

    async def trash(self, instance: Instance, ctype_id: str, file_name: str) -> str:
        ct = self._content_type(instance, ctype_id)
        folder = self._folder(instance, ct)
        file_name = Path(file_name).name
        trash_dir = self._trash_root / instance.id
        moved_to = await asyncio.to_thread(self._fs.move_to_trash, folder, file_name, trash_dir)
        await self._bus.publish("content.trashed", {"instance_id": instance.id, "file": file_name})
        return moved_to

    async def copy(
        self,
        source: Instance,
        target: Instance,
        ctype_id: str,
        file_name: str,
        target_ctype_id: str | None = None,
    ) -> None:
        """Copia um arquivo entre conjuntos de conteúdo.

        O tipo de destino pode diferir do de origem: é assim que um mod do
        servidor é levado para o perfil do cliente da mesma instância.
        """
        src_folder = self._folder(source, self._content_type(source, ctype_id))
        dst_folder = self._folder(
            target, self._content_type(target, target_ctype_id or ctype_id)
        )
        file_name = Path(file_name).name
        if src_folder == dst_folder:
            raise ValidationFailedError("origem e destino são a mesma pasta")
        await asyncio.to_thread(self._fs.copy, src_folder, file_name, dst_folder)
        await self._bus.publish(
            "content.copied",
            {"from": source.id, "to": target.id, "file": file_name},
        )

    async def compare(
        self,
        a: Instance,
        b: Instance,
        ctype_id: str,
        b_ctype_id: str | None = None,
    ) -> CompareResult:
        """Diferença entre dois conjuntos de conteúdo.

        Os lados são pares (instância, tipo) independentes. Com o mesmo tipo
        dos dois lados compara dois servidores; com tipos diferentes na mesma
        instância compara os mods do servidor com os do cliente, que é como se
        descobre incompatibilidade antes de o jogo crashar.
        """
        items_a = await self.list_content(a, ctype_id)
        items_b = await self.list_content(b, b_ctype_id or ctype_id)

        def key(item: ContentItem) -> str:
            return item.metadata.content_id or item.file.lower()

        map_a = {key(i): i for i in items_a}
        map_b = {key(i): i for i in items_b}

        only_a = [i for k, i in map_a.items() if k not in map_b]
        only_b = [i for k, i in map_b.items() if k not in map_a]
        diffs = [
            {
                "content_id": k,
                "a": {"file": map_a[k].file, "version": map_a[k].metadata.version},
                "b": {"file": map_b[k].file, "version": map_b[k].metadata.version},
            }
            for k in map_a.keys() & map_b.keys()
            if map_a[k].metadata.version != map_b[k].metadata.version
        ]
        return CompareResult(only_in_a=only_a, only_in_b=only_b, version_diffs=diffs)
