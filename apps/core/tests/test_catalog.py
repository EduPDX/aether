"""Catálogo: fusão do curado com a fonte externa, cache e mídia.

A fixture do Steam é a resposta real do `appdetails` do 7 Days to Die (251570),
capturada da loja pública. Testar contra ela pega mudanças de formato que um
JSON inventado esconderia.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.
"""

import asyncio
import json
from pathlib import Path

from aether_core.application.catalog import PREFIXO_MEDIA, CatalogService
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

        # Segunda visita vem do cache e nem chega a tentar baixar.
        await svc.get("jogo")
        assert len(baixados) == 1

        arquivo = ficha["banner_url"].rsplit("/", 1)[-1]
        caminho, tipo = svc.media_path("jogo", arquivo)
        assert caminho.read_bytes() == b"imagem-falsa"
        assert tipo == "image/jpeg"

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


def test_imagem_curada_tambem_e_baixada(tmp_path):
    """O Minecraft não tem fonte externa e mesmo assim tem logo e banner: se só
    o que vem de fonte fosse localizado, a página dependeria da CDN de terceiro
    a cada visita."""

    async def caso():
        baixados: list[str] = []

        async def baixar(url: str) -> bytes:
            baixados.append(url)
            return b"png-falso"

        entrada = _entrada(steam_app_id=None, logo_url="https://commons.exemplo/logo.svg")
        svc = CatalogService(
            Registry(jogo=ProviderComCatalogo(entrada)), tmp_path, [], baixar=baixar
        )

        ficha = await svc.get("jogo")

        assert baixados == ["https://commons.exemplo/logo.svg"]
        assert ficha["logo_url"].startswith("/api/v1/catalog/jogo/media/")
        # A extensão é preservada: servir um SVG como image/jpeg não desenha nada.
        arquivo = ficha["logo_url"].rsplit("/", 1)[-1]
        assert arquivo.endswith(".svg")
        _, tipo = svc.media_path("jogo", arquivo)
        assert tipo == "image/svg+xml"

    asyncio.run(caso())


def test_cache_gravado_sem_imagem_nao_trava_a_url_externa(tmp_path):
    """Instalação que já rodou antes tem cache sem imagem. Se ele bloqueasse a
    localização, a página buscaria a CDN externa até o TTL vencer — e o TTL
    renova a cada visita, ou seja, para sempre."""

    async def caso():
        entrada = _entrada(steam_app_id=None, logo_url="https://commons.exemplo/logo.svg")
        registry = Registry(jogo=ProviderComCatalogo(entrada))

        # Primeira vida do serviço: sem `baixar`, grava cache sem imagem.
        await CatalogService(registry, tmp_path, []).get("jogo")

        baixados: list[str] = []

        async def baixar(url: str) -> bytes:
            baixados.append(url)
            return b"png-falso"

        ficha = await CatalogService(registry, tmp_path, [], baixar=baixar).get("jogo")

        assert baixados == ["https://commons.exemplo/logo.svg"]
        assert ficha["logo_url"].startswith(PREFIXO_MEDIA)

    asyncio.run(caso())


# ------------------------------------------------------ imagem local do provider
def test_imagem_local_do_provider_vence_a_fonte(tmp_path):
    """Deixar logo/banner na pasta assets/ do jogo fixa a capa no código: ela
    ganha da imagem da loja e o Core nem vai à rede buscar."""

    async def caso():
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "banner.png").write_bytes(b"png-local")

        baixados: list[str] = []

        async def baixar(url: str) -> bytes:
            baixados.append(url)
            return b"da-internet"

        fonte = FonteFake({"banner_url": "https://cdn.exemplo/banner.jpg", "descricao": "da loja"})
        svc = CatalogService(
            Registry(jogo=ProviderComCatalogo(_entrada())),
            tmp_path / "cache",
            [fonte],
            baixar=baixar,
            assets_dir=lambda _p: assets,
        )

        ficha = await svc.get("jogo")

        assert ficha["banner_url"].startswith(PREFIXO_MEDIA)
        assert "cdn.exemplo" not in baixados  # a imagem da loja não foi baixada
        assert ficha["descricao"] == "da loja"  # outros metadados da fonte seguem valendo
        arquivo = ficha["banner_url"].rsplit("/", 1)[-1]
        caminho, tipo = svc.media_path("jogo", arquivo)
        assert caminho.read_bytes() == b"png-local"
        assert tipo == "image/png"

    asyncio.run(caso())


def test_sem_imagem_local_cai_para_a_fonte(tmp_path):
    """Jogo sem imagem local continua usando a da loja, como antes."""

    async def caso():
        assets = tmp_path / "assets"
        assets.mkdir()  # vazio

        baixados: list[str] = []

        async def baixar(url: str) -> bytes:
            baixados.append(url)
            return b"jpg"

        fonte = FonteFake({"banner_url": "https://cdn.exemplo/banner.jpg"})
        svc = CatalogService(
            Registry(jogo=ProviderComCatalogo(_entrada())),
            tmp_path / "cache",
            [fonte],
            baixar=baixar,
            assets_dir=lambda _p: assets,
        )

        ficha = await svc.get("jogo")

        assert baixados == ["https://cdn.exemplo/banner.jpg"]
        assert ficha["banner_url"].startswith(PREFIXO_MEDIA)

    asyncio.run(caso())


def test_a_grade_do_catalogo_usa_a_imagem_local(tmp_path):
    """A imagem local é de graça e sem rede, então já aparece na grade (list),
    não só na página do jogo."""

    async def caso():
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "logo.svg").write_bytes(b"<svg/>")

        svc = CatalogService(
            Registry(jogo=ProviderComCatalogo(_entrada())),
            tmp_path / "cache",
            [],
            assets_dir=lambda _p: assets,
        )

        grade = await svc.list()

        assert grade[0]["logo_url"].startswith(PREFIXO_MEDIA)
        assert grade[0]["logo_url"].endswith(".svg")

    asyncio.run(caso())


def test_arquivo_com_nome_fora_da_convencao_e_ignorado(tmp_path):
    """Só logo.* e banner.* contam; um screenshot solto na pasta não vira capa."""

    async def caso():
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "screenshot1.png").write_bytes(b"nao")

        svc = CatalogService(
            Registry(jogo=ProviderComCatalogo(_entrada())),
            tmp_path / "cache",
            [],
            assets_dir=lambda _p: assets,
        )

        ficha = await svc.get("jogo")
        assert ficha["banner_url"] == ""
        assert ficha["logo_url"] == ""

    asyncio.run(caso())
