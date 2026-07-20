"""Ports: abstract interfaces the application layer depends on.

Infrastructure provides the implementations; tests may provide fakes.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Protocol

from aether_sdk import ContainerSpec, GameProvider

from aether_core.domain.instances import Instance


class InstanceRepository(Protocol):
    async def add(self, instance: Instance) -> None: ...

    async def get(self, instance_id: str) -> Instance | None: ...

    async def list_all(self) -> list[Instance]: ...

    async def update_provider_data(self, instance_id: str, provider_data: dict) -> None: ...

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


# ------------------------------------------------------------------ containers


@dataclass
class ContainerLaunch:
    """Spec do provider + raiz da instância resolvida pelo Core.

    O provider declara volumes relativos (não conhece o host); é o Core que
    sabe onde a instância mora — este par é o que o supervisor Docker recebe.
    """

    spec: ContainerSpec
    root_dir: Path


@dataclass
class ManagedContainer:
    """Um container criado pelo Aether, identificado pelo label de instância."""

    container_id: str
    instance_id: str
    running: bool


@dataclass
class ContainerStats:
    """Consumo instantâneo de um container, já normalizado pelo runtime."""

    cpu_percent: float
    memory_bytes: int
    memory_limit_bytes: int


@dataclass
class ImageInfo:
    id: str
    tags: list[str]
    size_bytes: int


class ContainerRuntime(Protocol):
    """Abstração da engine de containers (Docker hoje).

    É a única fronteira do Core com o Docker: providers entregam um
    :class:`ContainerSpec` declarativo e o restante do sistema fala apenas
    com esta porta — regra de jogo nunca encosta na engine.
    """

    async def ensure_available(self) -> None:
        """Levanta ValidationFailedError com mensagem clara se a engine
        não estiver acessível (runtime process nunca chama isto)."""
        ...

    async def create(
        self, name: str, labels: dict[str, str], spec: ContainerSpec, root_dir: Path
    ) -> str:
        """Cria (substituindo homônimo parado) e devolve o id do container."""
        ...

    async def start(self, container_id: str) -> None: ...

    async def run_once(self, spec: ContainerSpec, root_dir: Path, on_line=None) -> tuple[int, str]:
        """Roda um container até o fim: instalar, atualizar, consultar versões.
        Devolve o código de saída e a saída completa; ``on_line`` acompanha
        cada linha enquanto ela sai."""
        ...

    async def stop(self, container_id: str, timeout: int) -> None: ...

    async def kill(self, container_id: str) -> None: ...

    async def write_stdin(self, container_id: str, data: str) -> None: ...

    def stream_logs(self, container_id: str) -> AsyncIterator[str]: ...

    async def wait(self, container_id: str) -> int:
        """Bloqueia até o container sair; devolve o exit code."""
        ...

    async def list_managed(self) -> list[ManagedContainer]: ...

    async def stats(self, container_id: str) -> ContainerStats | None: ...

    async def list_images(self) -> list[ImageInfo]: ...

    async def has_image(self, ref: str) -> bool:
        """A imagem já está no disco? O ``create`` da engine não baixa sozinho."""
        ...

    def pull_image(self, ref: str) -> AsyncIterator[dict]:
        """Puxa a imagem emitindo os eventos de progresso da engine."""
        ...

    async def remove_image(self, ref: str) -> None: ...
