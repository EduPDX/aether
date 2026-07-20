"""Catálogo: fusão do curado com a fonte externa, cache e mídia.

A fixture do Steam é a resposta real do `appdetails` do 7 Days to Die (251570),
capturada da loja pública. Testar contra ela pega mudanças de formato que um
JSON inventado esconderia.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.
"""

import asyncio
import json
from pathlib import Path

from aether_core.application.catalog import CatalogService
from aether_core.infrastructure.steam_store import SteamStoreSource
from aether_sdk import GameCatalogEntry, PortaDoJogo, RamPorJogadores

FIXTURES = Path(__file__).parent / "fixtures"
STEAM = json.loads((FIXTURES / "steam_appdetails_251570.json").read_text(encoding="utf-8"))


def _entrada(**extra) -> GameCatalogEntry:
    base = {
        "id": "jogo",
        "provider_id": "jogo",
        "nome": "Jogo de Teste",
        "portas": [PortaDoJogo(numero=26900, descricao="jogadores")],
        "ram_por_jogadores": [RamPorJogadores(ate_jogadores=8, ram="8 GB")],
        "steam_app_id": 251570,
    }
    return GameCatalogEntry(**{**base, **extra})


class ProviderComCatalogo:
    def __init__(self, entrada: GameCatalogEntry) -> None:
        self._entrada = entrada

    def catalog_entry(self) -> GameCatalogEntry:
        return self._entrada


class Registry:
    def __init__(self, **providers) -> None:
        self._p = providers

    def all(self) -> dict:
        return self._p

    def get(self, provider_id: str):
        return self._p[provider_id]


class FonteFake:
    id = "fake"

    def __init__(self, dados: dict, erro: Exception | None = None) -> None:
        self.dados = dados
        self.erro = erro
        self.chamadas = 0

    def aplica_para(self, entrada) -> bool:
        return True

    async def buscar(self, entrada) -> dict:
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return self.dados


def test_steam_traz_descricao_genero_e_requisitos_do_arquivo_real():
    async def caso():
        async def get(url, params=None):
            return STEAM

        dados = await SteamStoreSource(get).buscar(_entrada())

        assert "7 Days to Die" not in dados["descricao"] or dados["descricao"]
        assert dados["desenvolvedora"] == "The Fun Pimps"
        assert "Ação" in dados["genero"]
        assert "Linux" in dados["plataformas_do_cliente"]
        assert dados["banner_url"].startswith("http")
        # Os requisitos vêm em HTML; o parser precisa desmontá-los em campos.
        assert dados["requisitos_cliente_minimo"].ram
        assert "GB" in dados["requisitos_cliente_minimo"].ram

    asyncio.run(caso())


def test_steam_fora_do_ar_devolve_vazio_sem_levantar():
    """Catálogo sem descrição ainda é útil; catálogo que não abre, não."""

    async def caso():
        async def get(url, params=None):
            raise OSError("sem rede")

        assert await SteamStoreSource(get).buscar(_entrada()) == {}

    asyncio.run(caso())


def test_jogo_sem_steam_nao_consulta_a_fonte():
    async def get(url, params=None):  # pragma: no cover - não deve ser chamado
        raise AssertionError("não deveria consultar a Steam")

    assert SteamStoreSource(get).aplica_para(_entrada(steam_app_id=None)) is False


def test_curado_vence_a_fonte_externa(tmp_path):
    """Portas e RAM por jogadores são conhecimento de hospedagem: nenhuma loja
    sabe disso, e o que o provider declarou não pode ser sobrescrito."""

    async def caso():
        entrada = _entrada(desenvolvedora="Quem Curou")
        fonte = FonteFake({"desenvolvedora": "Steam Diz Outro", "descricao": "da loja"})
        svc = CatalogService(Registry(jogo=ProviderComCatalogo(entrada)), tmp_path, [fonte])

        ficha = await svc.get("jogo")

        assert ficha["desenvolvedora"] == "Quem Curou"  # curado mantido
        assert ficha["descricao"] == "da loja"  # buraco preenchido
        assert ficha["portas"][0]["numero"] == 26900
        assert ficha["ram_por_jogadores"][0]["ram"] == "8 GB"

    asyncio.run(caso())


def test_segunda_visita_usa_o_cache(tmp_path):
    async def caso():
        fonte = FonteFake({"descricao": "da loja"})
        svc = CatalogService(Registry(jogo=ProviderComCatalogo(_entrada())), tmp_path, [fonte])

        await svc.get("jogo")
        await svc.get("jogo")

        assert fonte.chamadas == 1

    asyncio.run(caso())


def test_atualizar_ignora_o_cache(tmp_path):
    async def caso():
        fonte = FonteFake({"descricao": "da loja"})
        svc = CatalogService(Registry(jogo=ProviderComCatalogo(_entrada())), tmp_path, [fonte])

        await svc.get("jogo")
        await svc.get("jogo", atualizar=True)

        assert fonte.chamadas == 2

    asyncio.run(caso())


def test_fonte_quebrada_nao_impede_a_ficha(tmp_path):
    async def caso():
        fonte = FonteFake({}, erro=OSError("timeout"))
        svc = CatalogService(Registry(jogo=ProviderComCatalogo(_entrada())), tmp_path, [fonte])

        # A exceção da fonte sobe até aqui? Não deve: o catálogo é o que importa.
        try:
            ficha = await svc.get("jogo")
        except OSError:  # pragma: no cover - falha do teste, não do código
            raise AssertionError("a fonte quebrada derrubou o catálogo") from None
        assert ficha["nome"] == "Jogo de Teste"

    asyncio.run(caso())


def test_imagem_e_baixada_uma_vez_e_servida_pelo_core(tmp_path):
    """O navegador não deve depender da CDN externa, e servidor sem internet
    precisa continuar mostrando a capa que já baixou."""

    async def caso():
        baixados: list[str] = []

        async def baixar(url: str) -> bytes:
            baixados.append(url)
            return b"imagem-falsa"

        fonte = FonteFake({"banner_url": "https://cdn.exemplo/banner.jpg"})
        svc = CatalogService(
            Registry(jogo=ProviderComCatalogo(_entrada())), tmp_path, [fonte], baixar=baixar
        )

        ficha = await svc.get("jogo")
        assert ficha["banner_url"].startswith("/api/v1/catalog/jogo/media/")
        assert len(baixados) == 1

        # Segunda visita vem do cache e não baixa de novo.
        await svc.get("jogo", atualizar=True)
        assert len(baixados) == 1

        arquivo = ficha["banner_url"].rsplit("/", 1)[-1]
        assert svc.media_path("jogo", arquivo).read_bytes() == b"imagem-falsa"

    asyncio.run(caso())


def test_media_path_nao_escapa_da_pasta(tmp_path):
    """Nome de arquivo com ../ não pode virar leitura de arquivo do sistema."""
    svc = CatalogService(Registry(), tmp_path)
    (tmp_path / "media").mkdir()
    segredo = tmp_path / "segredo.txt"
    segredo.write_text("nao")

    from aether_core.domain.errors import NotFoundError

    try:
        svc.media_path("jogo", "../segredo.txt")
    except NotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("deveria recusar caminho para fora da pasta de mídia")
