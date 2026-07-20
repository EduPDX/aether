"""File explorer use cases, sandboxed to the instance root.

Every path is resolved against the instance root; anything escaping it is
rejected. Deletes go to the trash, never straight to oblivion. Text
editing is capped to protect the UI (and the server) from huge files.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.application.trash import TrashService
from aether_core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from aether_core.domain.instances import Instance
from aether_core.domain.trash import TrashOrigin


class _StreamSink:
    """Destino de escrita do zipfile que acumula bytes para serem emitidos.

    O zipfile aceita um objeto sem `seek` desde que `tell` exista — nesse modo
    ele grava descritores de dados em vez de voltar para corrigir cabeçalhos,
    que é justamente o que permite gerar o arquivo em fluxo.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._pos = 0

    def write(self, data: bytes) -> int:
        self._buf.extend(data)
        self._pos += len(data)
        return len(data)

    def tell(self) -> int:
        return self._pos

    def flush(self) -> None:
        pass

    @property
    def pending(self) -> int:
        return len(self._buf)

    def drain(self) -> bytes:
        pedaco = bytes(self._buf)
        self._buf.clear()
        return pedaco


MAX_TEXT_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_UPLOAD_BYTES = 512 * 1024 * 1024  # 512 MB por arquivo


@dataclass
class FileEntryInfo:
    name: str
    is_dir: bool
    size: int
    mtime: int


class FilesService:
    def __init__(self, trash: TrashService, bus: EventBus) -> None:
        self._trash = trash
        self._bus = bus

    # -------------------------------------------------------------- sandbox --
    @staticmethod
    def _resolve(instance: Instance, rel_path: str) -> Path:
        # Backslash is always treated as a separator (even on Linux) so a
        # Windows-style traversal string can never be a valid file name.
        rel_path = rel_path.replace("\\", "/").lstrip("/")
        root = Path(instance.root_dir).resolve()
        target = (root / rel_path).resolve()
        if target != root and root not in target.parents:
            raise ForbiddenError("path escapes the instance directory")
        return target

    # ------------------------------------------------------------ use cases --
    async def list_dir(self, instance: Instance, rel_path: str) -> list[FileEntryInfo]:
        target = self._resolve(instance, rel_path)

        def _list() -> list[FileEntryInfo]:
            if not target.is_dir():
                raise NotFoundError(f"directory not found: {rel_path or '/'}")
            entries: list[FileEntryInfo] = []
            for p in target.iterdir():
                try:
                    st = p.stat()
                except OSError:
                    continue
                entries.append(
                    FileEntryInfo(
                        name=p.name,
                        is_dir=p.is_dir(),
                        size=0 if p.is_dir() else st.st_size,
                        mtime=int(st.st_mtime),
                    )
                )
            entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
            return entries

        return await asyncio.to_thread(_list)

    async def read_text(self, instance: Instance, rel_path: str) -> str:
        target = self._resolve(instance, rel_path)

        def _read() -> str:
            if not target.is_file():
                raise NotFoundError(f"file not found: {rel_path}")
            if target.stat().st_size > MAX_TEXT_BYTES:
                raise ValidationFailedError("file is too large for the editor (max 2 MB)")
            data = target.read_bytes()
            if b"\x00" in data[:8192]:
                raise ValidationFailedError("binary files cannot be opened in the editor")
            return data.decode("utf-8", "replace")

        return await asyncio.to_thread(_read)

    async def write_text(self, instance: Instance, rel_path: str, content: str) -> None:
        target = self._resolve(instance, rel_path)
        if len(content.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValidationFailedError("content is too large (max 2 MB)")

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")

        await asyncio.to_thread(_write)
        await self._bus.publish("files.written", {"instance_id": instance.id, "path": rel_path})

    async def save_upload(
        self,
        instance: Instance,
        rel_dir: str,
        filename: str,
        chunks: AsyncIterator[bytes],
        *,
        overwrite: bool = False,
    ) -> dict:
        """Streams an uploaded file into ``rel_dir`` (never leaves the sandbox).

        ``chunks`` is any async iterable of bytes, so the application layer
        stays independent of the web framework.
        """
        name = Path(filename).name
        if not name or name.startswith("."):
            raise ValidationFailedError(f"nome de arquivo inválido: {filename!r}")

        target_dir = self._resolve(instance, rel_dir)
        if not target_dir.is_dir():
            raise NotFoundError(f"pasta de destino não existe: {rel_dir or '/'}")
        dest = target_dir / name
        if dest.exists() and not overwrite:
            raise ConflictError(f"já existe um arquivo com esse nome: {name}")

        tmp = dest.with_name(dest.name + ".aether-upload")
        written = 0
        try:
            with tmp.open("wb") as f:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise ValidationFailedError(
                            f"arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                        )
                    await asyncio.to_thread(f.write, chunk)
            await asyncio.to_thread(tmp.replace, dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

        await self._bus.publish(
            "files.uploaded",
            {"instance_id": instance.id, "path": f"{rel_dir}/{name}".lstrip("/"), "size": written},
        )
        return {"name": name, "size": written}

    async def resolve_download(self, instance: Instance, rel_path: str) -> tuple[Path, bool]:
        """Caminho a baixar e se é pasta (que vira zip). Sempre no sandbox."""
        target = self._resolve(instance, rel_path)
        if not target.exists():
            raise NotFoundError(f"não encontrado: {rel_path}")
        return target, target.is_dir()

    def stream_zip(self, instance: Instance, rel_path: str) -> Iterator[bytes]:
        """Compacta uma pasta emitindo os bytes conforme são gerados.

        A versão anterior escrevia o zip inteiro em /tmp antes de responder o
        primeiro byte. Num mundo de vários GB isso significava minutos de
        silêncio (o usuário achava que não tinha funcionado), o dobro de espaço
        em disco e o navegador sem barra de progresso.

        Usa ZIP_STORED: o grosso de um mundo são arquivos de região, que já são
        comprimidos internamente. Recomprimir gastaria muito CPU para ganhar
        quase nada e atrasaria o início do download.
        """
        import zipfile

        folder = self._resolve(instance, rel_path)
        if not folder.is_dir():
            raise NotFoundError(f"pasta não encontrada: {rel_path}")

        sink = _StreamSink()
        # allowZip64: mundos passam de 4 GB e do limite de 65.535 arquivos.
        with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for path in sorted(folder.rglob("*")):
                if not path.is_file():
                    continue
                arc = path.relative_to(folder).as_posix()
                try:
                    with zf.open(arc, "w") as destino, open(path, "rb") as origem:
                        while pedaco := origem.read(1 << 20):
                            destino.write(pedaco)
                            if sink.pending >= (1 << 18):
                                yield sink.drain()
                except (OSError, PermissionError):
                    # Arquivo sumiu ou está travado no meio da varredura: pular
                    # é melhor que abortar um download de gigabytes.
                    continue
                if sink.pending:
                    yield sink.drain()
        yield sink.drain()  # diretório central, escrito no close

    async def mkdir(self, instance: Instance, rel_path: str) -> None:
        target = self._resolve(instance, rel_path)
        if target.exists():
            raise ConflictError(f"already exists: {rel_path}")
        await asyncio.to_thread(target.mkdir, parents=True)

    async def rename(self, instance: Instance, rel_path: str, new_name: str) -> None:
        if "/" in new_name or "\\" in new_name or not new_name.strip():
            raise ValidationFailedError("invalid name")
        source = self._resolve(instance, rel_path)
        if not source.exists():
            raise NotFoundError(f"not found: {rel_path}")
        target = source.with_name(new_name)
        if target.exists():
            raise ConflictError(f"already exists: {new_name}")
        await asyncio.to_thread(source.rename, target)

    async def delete(self, instance: Instance, rel_path: str) -> str:
        """Move para a lixeira — de onde dá para voltar, via TrashService."""
        source = self._resolve(instance, rel_path)
        if source == Path(instance.root_dir).resolve():
            raise ForbiddenError("cannot delete the instance root")
        if not source.exists():
            raise NotFoundError(f"not found: {rel_path}")

        item = await self._trash.store(instance, source, rel_path, origin=TrashOrigin.FILES)
        await self._bus.publish("files.trashed", {"instance_id": instance.id, "path": rel_path})
        return item.id
