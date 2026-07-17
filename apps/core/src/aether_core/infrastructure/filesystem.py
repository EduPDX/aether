"""Local filesystem implementations of content-related ports."""

import fnmatch
import hashlib
import os
import shutil
from pathlib import Path

from aether_core.application.ports import FileEntry
from aether_core.domain.errors import (
    ContentFileNotFoundError,
    ContentFolderMissingError,
    TargetExistsError,
)


class LocalContentFilesystem:
    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def scan(self, folder: Path, patterns: list[str]) -> list[FileEntry]:
        lowered = [p.lower() for p in patterns]
        entries: list[FileEntry] = []
        for name in sorted(os.listdir(folder), key=str.lower):
            if not any(fnmatch.fnmatch(name.lower(), p) for p in lowered):
                continue
            full = folder / name
            try:
                st = full.stat()
            except OSError:
                continue
            if not full.is_file():
                continue
            entries.append(FileEntry(name=name, size=st.st_size, mtime=int(st.st_mtime)))
        return entries

    def _existing(self, folder: Path, name: str) -> Path:
        full = folder / Path(name).name
        if not full.is_file():
            raise ContentFileNotFoundError(f"file not found: {full.name}")
        return full

    def rename(self, folder: Path, old_name: str, new_name: str) -> None:
        src = self._existing(folder, old_name)
        dst = folder / Path(new_name).name
        if dst.exists():
            raise TargetExistsError(f"target already exists: {dst.name}")
        os.rename(src, dst)

    def move_to_trash(self, folder: Path, name: str, trash_dir: Path) -> str:
        src = self._existing(folder, name)
        trash_dir.mkdir(parents=True, exist_ok=True)
        dest = trash_dir / src.name
        base, i = dest, 1
        while dest.exists():
            dest = Path(f"{base}.{i}")
            i += 1
        shutil.move(str(src), str(dest))
        return str(dest)

    def copy(self, src_folder: Path, name: str, dst_folder: Path) -> None:
        src = self._existing(src_folder, name)
        if not dst_folder.is_dir():
            raise ContentFolderMissingError(f"destination folder does not exist: {dst_folder}")
        shutil.copy2(src, dst_folder / src.name)


class FileIconStore:
    """Content-addressed icon storage (sha1 of the bytes)."""

    def __init__(self, icons_dir: Path) -> None:
        self._dir = icons_dir

    def save(self, png: bytes) -> str:
        name = hashlib.sha1(png).hexdigest()[:20] + ".png"
        path = self._dir / name
        if not path.exists():
            self._dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
        return name

    def path(self, name: str) -> Path:
        return self._dir / Path(name).name
