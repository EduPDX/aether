"""Catálogo de conteúdo — buscar, instalar e detectar atualizações.

Modrinth e CurseForge são catálogos de Minecraft, mas o conceito não é: o
Factorio tem o Mod Portal, o Zomboid usa a Workshop da Steam. O Core sabe
buscar, baixar, verificar integridade e comparar versões; o provider diz de
quais catálogos aquele jogo dispõe e como falar com eles.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SourceItem:
    """Um projeto no catálogo (ainda não é um arquivo)."""

    source_id: str
    project_id: str
    slug: str
    name: str
    summary: str = ""
    author: str = ""
    downloads: int = 0
    icon_url: str | None = None
    page_url: str | None = None
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceDependency:
    project_id: str
    """required, optional, incompatible ou embedded."""
    kind: str = "required"


@dataclass(frozen=True)
class SourceVersion:
    """Um arquivo publicado de um projeto."""

    source_id: str
    project_id: str
    version_id: str
    version_number: str
    file_name: str
    download_url: str
    size: int = 0
    """Hashes publicados pelo catálogo — o download é verificado contra eles."""
    sha1: str | None = None
    sha512: str | None = None
    game_versions: tuple[str, ...] = ()
    loaders: tuple[str, ...] = ()
    dependencies: tuple[SourceDependency, ...] = field(default_factory=tuple)
    released_at: datetime | None = None
    changelog: str = ""


@runtime_checkable
class ContentSource(Protocol):
    """Um catálogo consultável de conteúdo para um jogo."""

    id: str
    label: str
    """Se exige credencial do usuário (CurseForge exige, Modrinth não)."""
    requires_api_key: bool

    async def search(
        self,
        query: str,
        *,
        game_version: str | None = None,
        loader: str | None = None,
        categories: tuple[str, ...] = (),
        limit: int = 20,
        offset: int = 0,
    ) -> list[SourceItem]: ...

    def available_categories(self) -> tuple[tuple[str, str], ...]:
        """Categorias filtráveis como (id, rótulo). Vazio = não suporta."""
        ...

    async def versions(
        self,
        project_id: str,
        *,
        game_version: str | None = None,
        loader: str | None = None,
    ) -> list[SourceVersion]: ...

    async def lookup_by_hash(self, sha1: str) -> SourceVersion | None:
        """Identifica um arquivo já instalado pelo hash.

        É o que permite dizer "este .jar é o Sodium 0.5.3 e existe 0.5.8"
        sem depender do nome do arquivo, que o usuário pode ter renomeado.
        """
        ...
