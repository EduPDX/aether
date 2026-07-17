"""Ports: abstract interfaces the application layer depends on.

Infrastructure provides the implementations; tests may provide fakes.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Protocol

from aether_sdk import GameProvider

from aether_core.domain.instances import Instance


class InstanceRepository(Protocol):
    async def add(self, instance: Instance) -> None: ...

    async def get(self, instance_id: str) -> Instance | None: ...

    async def list_all(self) -> list[Instance]: ...

    async def delete(self, instance_id: str) -> bool: ...


class ProviderRegistry(Protocol):
    def get(self, provider_id: str) -> GameProvider:
        """Raises ProviderNotFoundError for unknown ids."""
        ...

    def all(self) -> dict[str, GameProvider]: ...


class FileEntry(NamedTuple):
    name: str
    size: int
    mtime: int


class ContentFilesystem(Protocol):
    """Filesystem operations on content folders (names are always basenames)."""

    def is_dir(self, path: Path) -> bool: ...

    def scan(self, folder: Path, patterns: list[str]) -> list[FileEntry]: ...

    def rename(self, folder: Path, old_name: str, new_name: str) -> None: ...

    def move_to_trash(self, folder: Path, name: str, trash_dir: Path) -> str: ...

    def copy(self, src_folder: Path, name: str, dst_folder: Path) -> None: ...


@dataclass
class CachedContent:
    metadata: dict
    icon_file: str | None


class ContentCache(Protocol):
    async def get_many(self, keys: list[str]) -> dict[str, CachedContent]: ...

    async def put_many(self, entries: dict[str, CachedContent]) -> None: ...


class IconStore(Protocol):
    def save(self, png: bytes) -> str:
        """Store icon bytes, return a stable file name."""
        ...

    def path(self, name: str) -> Path: ...
