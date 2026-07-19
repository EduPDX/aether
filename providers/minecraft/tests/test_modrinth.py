"""Cliente Modrinth — sem rede: o transporte HTTP é injetado.

Um catálogo testado só contra a API real quebra em silêncio quando ela muda e
não dá para exercitar os casos estranhos (versão sem arquivo primário, hash
desconhecido, campo ausente).
"""

import asyncio
import json

from aether_provider_minecraft.content.modrinth import ModrinthSource

BUSCA = {
    "hits": [
        {
            "project_id": "AANobbMI",
            "slug": "sodium",
            "title": "Sodium",
            "description": "Otimização de renderização",
            "author": "jellysquid3",
            "downloads": 12_000_000,
            "icon_url": "https://cdn.modrinth.com/sodium.png",
            "categories": ["optimization", "fabric"],
        }
    ]
}

VERSAO = {
    "id": "vvvv1111",
    "project_id": "AANobbMI",
    "version_number": "0.5.8",
    "date_published": "2026-03-04T18:20:11Z",
    "game_versions": ["1.20.1"],
    "loaders": ["fabric"],
    "changelog": "correções",
    "dependencies": [
        {"project_id": "P7dR8mSH", "dependency_type": "required"},
        {"project_id": "XXXXXXXX", "dependency_type": "optional"},
        {"project_id": None, "dependency_type": "required"},
    ],
    "files": [
        {"filename": "sources.jar", "url": "u/sources", "primary": False, "size": 1, "hashes": {}},
        {
            "filename": "sodium-0.5.8.jar",
            "url": "https://cdn.modrinth.com/sodium-0.5.8.jar",
            "primary": True,
            "size": 412_000,
            "hashes": {"sha1": "abc123", "sha512": "def456"},
        },
    ],
}


class _HttpFalso:
    def __init__(self, respostas: dict[str, object]) -> None:
        self.respostas = respostas
        self.chamadas: list[tuple[str, dict | None]] = []

    async def __call__(self, url, params=None):
        self.chamadas.append((url, params))
        for chave, valor in self.respostas.items():
            if chave in url:
                return valor
        return None


def test_search_maps_fields_and_builds_facets():
    http = _HttpFalso({"/search": BUSCA})
    fonte = ModrinthSource(http)

    itens = asyncio.run(fonte.search("sodium", game_version="1.20.1", loader="Forge"))

    assert len(itens) == 1
    item = itens[0]
    assert (item.source_id, item.project_id, item.name) == ("modrinth", "AANobbMI", "Sodium")
    assert item.downloads == 12_000_000
    assert item.page_url == "https://modrinth.com/mod/sodium"

    # as facetas filtram por tipo, versão do jogo e loader (em minúsculas)
    _, params = http.chamadas[0]
    facetas = json.loads(params["facets"])
    assert ["project_type:mod"] in facetas
    assert ["versions:1.20.1"] in facetas
    assert ["categories:forge"] in facetas


def test_version_uses_the_primary_file():
    """Uma versão lista jar, sources e javadoc — instalar o errado quebraria."""
    http = _HttpFalso({"/version": [VERSAO]})
    versoes = asyncio.run(ModrinthSource(http).versions("AANobbMI"))

    v = versoes[0]
    assert v.file_name == "sodium-0.5.8.jar"
    assert v.download_url.endswith("sodium-0.5.8.jar")
    assert v.size == 412_000
    assert (v.sha1, v.sha512) == ("abc123", "def456")
    assert v.version_number == "0.5.8"
    assert v.game_versions == ("1.20.1",)


def test_dependencies_without_project_id_are_dropped():
    http = _HttpFalso({"/version": [VERSAO]})
    v = asyncio.run(ModrinthSource(http).versions("AANobbMI"))[0]

    assert [d.project_id for d in v.dependencies] == ["P7dR8mSH", "XXXXXXXX"]
    assert [d.kind for d in v.dependencies] == ["required", "optional"]


def test_versions_come_newest_first():
    antiga = {
        **VERSAO,
        "id": "old",
        "version_number": "0.5.0",
        "date_published": "2025-01-01T00:00:00Z",
    }
    http = _HttpFalso({"/version": [antiga, VERSAO]})
    versoes = asyncio.run(ModrinthSource(http).versions("AANobbMI"))
    assert [v.version_number for v in versoes] == ["0.5.8", "0.5.0"]


def test_unknown_hash_returns_none():
    """Mod que não está no catálogo (privado, modpack) não pode virar erro."""
    http = _HttpFalso({})
    assert asyncio.run(ModrinthSource(http).lookup_by_hash("naoexiste")) is None


def test_lookup_by_hash_identifies_an_installed_file():
    http = _HttpFalso({"/version_file/": VERSAO})
    v = asyncio.run(ModrinthSource(http).lookup_by_hash("abc123"))
    assert v is not None
    assert v.project_id == "AANobbMI"
    assert v.version_number == "0.5.8"
    url, params = http.chamadas[0]
    assert params == {"algorithm": "sha1"}


def test_version_without_files_does_not_crash():
    """Resposta degenerada do catálogo não pode derrubar a listagem."""
    http = _HttpFalso({"/version": [{**VERSAO, "files": []}]})
    v = asyncio.run(ModrinthSource(http).versions("AANobbMI"))[0]
    assert v.file_name == ""
    assert v.download_url == ""
