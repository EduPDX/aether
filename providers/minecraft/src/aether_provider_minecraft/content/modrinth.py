"""Catálogo Modrinth.

API aberta e sem credencial, por isso é o catálogo padrão. O transporte HTTP
é injetado para os testes não dependerem de rede — um catálogo testado só
contra a internet real quebra em silêncio quando a API muda.
"""

from datetime import datetime
from typing import Any, Protocol

from aether_sdk import SourceDependency, SourceItem, SourceVersion

BASE = "https://api.modrinth.com/v2"
SOURCE_ID = "modrinth"

# Modrinth fala "required/optional/incompatible/embedded"; o SDK usa os mesmos
# termos, então o mapa existe só para normalizar o que vier fora do esperado.
_TIPOS = {"required", "optional", "incompatible", "embedded"}


class HttpGet(Protocol):
    async def __call__(self, url: str, params: dict[str, Any] | None = None) -> Any: ...


class HttpPost(Protocol):
    async def __call__(self, url: str, json: dict[str, Any]) -> Any: ...


def _data(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _facets(game_version: str | None, loader: str | None) -> str | None:
    """Facetas do Modrinth: lista de listas, AND entre grupos, OR dentro."""
    grupos: list[list[str]] = [["project_type:mod"]]
    if game_version:
        grupos.append([f"versions:{game_version}"])
    if loader:
        grupos.append([f"categories:{loader.lower()}"])
    import json

    return json.dumps(grupos)


def _versao(payload: dict) -> SourceVersion:
    arquivos = payload.get("files") or []
    # O catálogo pode listar vários arquivos por versão (jar, sources, javadoc);
    # o "primary" é o que se instala.
    principal = next((f for f in arquivos if f.get("primary")), arquivos[0] if arquivos else {})
    hashes = principal.get("hashes") or {}
    deps = tuple(
        SourceDependency(
            project_id=str(d.get("project_id") or ""),
            kind=(d.get("dependency_type") if d.get("dependency_type") in _TIPOS else "required"),
        )
        for d in (payload.get("dependencies") or [])
        if d.get("project_id")
    )
    return SourceVersion(
        source_id=SOURCE_ID,
        project_id=str(payload.get("project_id") or ""),
        version_id=str(payload.get("id") or ""),
        version_number=str(payload.get("version_number") or ""),
        file_name=str(principal.get("filename") or ""),
        download_url=str(principal.get("url") or ""),
        size=int(principal.get("size") or 0),
        sha1=hashes.get("sha1"),
        sha512=hashes.get("sha512"),
        game_versions=tuple(payload.get("game_versions") or ()),
        loaders=tuple(payload.get("loaders") or ()),
        dependencies=deps,
        released_at=_data(payload.get("date_published")),
        changelog=str(payload.get("changelog") or "")[:2000],
    )


class ModrinthSource:
    id = SOURCE_ID
    label = "Modrinth"
    requires_api_key = False

    def __init__(self, http: HttpGet, http_post: HttpPost | None = None, base: str = BASE) -> None:
        self._http = http
        self._post = http_post
        self._base = base.rstrip("/")

    async def _http_post(self, url: str, json: dict[str, Any]) -> Any:
        if self._post is None:
            return None
        return await self._post(url, json)

    async def search(
        self,
        query: str,
        *,
        game_version: str | None = None,
        loader: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SourceItem]:
        params: dict[str, Any] = {"query": query, "limit": limit, "offset": offset}
        facetas = _facets(game_version, loader)
        if facetas:
            params["facets"] = facetas
        corpo = await self._http(f"{self._base}/search", params)
        return [
            SourceItem(
                source_id=SOURCE_ID,
                project_id=str(h.get("project_id") or ""),
                slug=str(h.get("slug") or ""),
                name=str(h.get("title") or ""),
                summary=str(h.get("description") or ""),
                author=str(h.get("author") or ""),
                downloads=int(h.get("downloads") or 0),
                icon_url=h.get("icon_url") or None,
                page_url=f"https://modrinth.com/mod/{h.get('slug')}" if h.get("slug") else None,
                categories=tuple(h.get("categories") or ()),
            )
            for h in (corpo.get("hits") or [])
        ]

    async def versions(
        self,
        project_id: str,
        *,
        game_version: str | None = None,
        loader: str | None = None,
    ) -> list[SourceVersion]:
        import json

        params: dict[str, Any] = {}
        if game_version:
            params["game_versions"] = json.dumps([game_version])
        if loader:
            params["loaders"] = json.dumps([loader.lower()])
        corpo = await self._http(f"{self._base}/project/{project_id}/version", params)
        versoes = [_versao(v) for v in (corpo or [])]
        # Mais recente primeiro: a interface mostra a candidata no topo.
        versoes.sort(key=lambda v: v.released_at or datetime.min, reverse=True)
        return versoes

    async def version_by_id(self, version_id: str) -> SourceVersion | None:
        """Uma versão específica — o que a instalação recebe da interface."""
        corpo = await self._http(f"{self._base}/version/{version_id}")
        return _versao(corpo) if corpo else None

    async def lookup_by_hash(self, sha1: str) -> SourceVersion | None:
        corpo = await self._http(
            f"{self._base}/version_file/{sha1}", {"algorithm": "sha1"}
        )
        return _versao(corpo) if corpo else None

    async def lookup_many(self, hashes: list[str]) -> dict[str, SourceVersion]:
        """Identifica vários arquivos numa requisição só.

        Uma instalação real tem centenas de mods; consultar um a um seria
        centenas de chamadas e esbarraria no limite de taxa do catálogo. O
        Modrinth expõe um endpoint em lote — o serviço usa este método quando
        o catálogo o oferece e cai no unitário quando não.
        """
        if not hashes:
            return {}
        corpo = await self._http_post(
            f"{self._base}/version_files",
            {"hashes": hashes, "algorithm": "sha1"},
        )
        return {h: _versao(v) for h, v in (corpo or {}).items() if v}
