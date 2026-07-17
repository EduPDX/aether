"""File explorer use cases, sandboxed to the instance root.

Every path is resolved against the instance root; anything escaping it is
rejected. Deletes go to the trash, never straight to oblivion. Text
editing is capped to protect the UI (and the server) from huge files.
"""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from aether_core.domain.instances import Instance

MAX_TEXT_BYTES = 2 * 1024 * 1024  # 2 MB


@dataclass
class FileEntryInfo:
    name: str
    is_dir: bool
    size: int
    mtime: int


class FilesService:
    def __init__(self, trash_root: Path, bus: EventBus) -> None:
        self._trash_root = trash_root
        self._bus = bus

    # -------------------------------------------------------------- sandbox --
    @staticmethod
    def _resolve(instance: Instance, rel_path: str) -> Path:
        root = Path(instance.root_dir).resolve()
        target = (root / rel_path.lstrip("/\\")).resolve()
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
        source = self._resolve(instance, rel_path)
        if source == Path(instance.root_dir).resolve():
            raise ForbiddenError("cannot delete the instance root")
        if not source.exists():
            raise NotFoundError(f"not found: {rel_path}")

        def _trash() -> str:
            trash_dir = self._trash_root / instance.id / "files"
            trash_dir.mkdir(parents=True, exist_ok=True)
            dest = trash_dir / source.name
            base, i = dest, 1
            while dest.exists():
                dest = Path(f"{base}.{i}")
                i += 1
            shutil.move(str(source), str(dest))
            return str(dest)

        moved_to = await asyncio.to_thread(_trash)
        await self._bus.publish("files.trashed", {"instance_id": instance.id, "path": rel_path})
        return moved_to
