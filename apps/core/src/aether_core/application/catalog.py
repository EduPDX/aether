"""Catálogo de jogos: junta o que o provider curou com o que a fonte externa sabe.

A precedência é sempre do provider. O que ele declara é conhecimento de
hospedagem — portas, RAM por jogadores, avisos — e nenhuma loja de jogos sabe
disso. A fonte externa só preenche buracos: descrição, gênero, desenvolvedora,
requisitos do cliente e imagens.

Três decisões que evitam surpresa em produção:

- **imagem local vence.** Se o provider traz `logo.*`/`banner.*` na sua pasta
  `assets/`, é ela que aparece — sem tocar na rede. É como fixar a capa de um
  jogo no próprio código.
- **cache em disco.** A tela do catálogo abre sem rede e não bate na Steam a
  cada visita.
- **imagens baixadas.** Sem imagem local, a da loja é baixada uma vez e servida
  pelo Core; o navegador do usuário nunca fala com a CDN externa.
"""

import asyncio
import hashlib
import importlib.resources as resources
import json
import logging
import time
from pathlib import Path

from aether_sdk import GameCatalogEntry, SupportsCatalog

from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import NotFoundError

log = logging.getLogger(__name__)

TTL_SEGUNDOS = 7 * 24 * 3600
"""Metadados de jogo mudam devagar; uma semana evita tráfego inútil."""

IMAGENS = ("banner_url", "logo_url")
PREFIXO_MEDIA = "/api/v1/catalog/"

ASSET_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")
"""Formatos aceitos para uma imagem local; o arquivo tem de se chamar
exatamente ``logo.<ext>`` ou ``banner.<ext>``."""


def _assets_do_pacote(provider):
    """Pasta ``assets/`` do pacote do provider, onde ele pode deixar as imagens.

    Resolvido por ``importlib.resources`` (e não por ``__file__``) para funcionar
    tanto com o provider instalado do código-fonte quanto empacotado num wheel.
    """
    pacote = type(provider).__module__.split(".")[0]
    try:
        return resources.files(pacote) / "assets"
    except (ModuleNotFoundError, TypeError):
        return None


class CatalogService:
    def __init__(
        self,
        providers: ProviderRegistry,
        cache_dir: Path,
        fontes: list | None = None,
        baixar=None,
        assets_dir=_assets_do_pacote,
    ) -> None:
        self._providers = providers
        self._dir = Path(cache_dir)
        self._fontes = fontes or []
        self._baixar = baixar
        # Como achar a pasta de imagens de um provider; injetável para teste.
        self._assets_dir = assets_dir

    @property
    def media_dir(self) -> Path:
        return self._dir / "media"

    # ------------------------------------------------------------------ leitura
    def _curados(self) -> dict[str, GameCatalogEntry]:
        entradas: dict[str, GameCatalogEntry] = {}
        for provider_id, provider in self._providers.all().items():
            if not isinstance(provider, SupportsCatalog):
                continue
            try:
                entrada = provider.catalog_entry()
            except Exception:  # noqa: BLE001 - provider quebrado não derruba o catálogo
                log.exception("provider %s falhou ao descrever o jogo", provider_id)
                continue
            entradas[entrada.id] = entrada
        return entradas

    async def list(self) -> list[dict]:
        """Lista para a grade do catálogo — usa só o cache, sem ir à rede.

        A grade precisa abrir rápido; a página do jogo é que busca o que falta.
        """
        saida = []
        for entrada in self._curados().values():
            dados = self._ler_cache(entrada.id) or {}
            # Imagem local é de graça e não depende de rede, então entra já na
            # grade — não só na página do jogo.
            dados = self._localizar_assets(entrada, dados)
            saida.append(self._aplicar(entrada, dados).model_dump())
        return saida

    async def get(self, game_id: str, *, atualizar: bool = False) -> dict:
        entradas = self._curados()
        entrada = entradas.get(game_id)
        if entrada is None:
            raise NotFoundError(f"jogo não encontrado no catálogo: {game_id}")

        extra = None if atualizar else self._ler_cache(game_id)
        if extra is None:
            extra = await self._buscar_nas_fontes(entrada)

        # Imagem local do provider vem primeiro e vence a da loja: se você deixou
        # logo/banner na pasta assets/ do jogo, é ela que aparece, sem rede.
        # Roda mesmo com cache quente para refletir na hora a troca da imagem.
        extra = self._localizar_assets(entrada, extra or {})

        # O que sobrar apontando para a internet é baixado e servido pelo Core.
        # Sem isso a página dependeria de uma CDN de terceiro a cada visita, e um
        # cache gravado antes de a imagem existir travaria a URL externa até o TTL
        # vencer — numa instalação já rodando, para sempre na prática.
        final = self._aplicar(entrada, extra)
        if self._falta_localizar(final):
            extra = await self._localizar_imagens(final, extra)
            final = self._aplicar(entrada, extra)
        self._gravar_cache(game_id, extra)
        return final.model_dump()

    @staticmethod
    def _falta_localizar(final: GameCatalogEntry) -> bool:
        return any(str(getattr(final, campo, "")).startswith("http") for campo in IMAGENS)

    # ------------------------------------------------------------------ fusão
    @staticmethod
    def _aplicar(entrada: GameCatalogEntry, extra: dict) -> GameCatalogEntry:
        """Preenche apenas o que o provider deixou vazio."""
        if not extra:
            return entrada
        dados = entrada.model_dump()
        for chave, valor in extra.items():
            if chave not in dados or not valor:
                continue
            atual = dados.get(chave)
            if atual in (None, "", [], {}):
                dados[chave] = valor
            elif chave in IMAGENS and str(valor).startswith(PREFIXO_MEDIA):
                # Exceção estreita: aqui o extra não está discordando do provider,
                # é a mesma imagem que ele declarou, já baixada e servida por nós.
                dados[chave] = valor
        return GameCatalogEntry.model_validate(dados)

    async def _buscar_nas_fontes(self, entrada: GameCatalogEntry) -> dict:
        reunido: dict = {}
        for fonte in self._fontes:
            if not fonte.aplica_para(entrada):
                continue
            try:
                dados = await fonte.buscar(entrada)
            except Exception:  # noqa: BLE001 - fonte externa nunca derruba o catálogo
                # Não dá para confiar que toda fonte trate os próprios erros:
                # a de hoje trata, a de amanhã pode não tratar.
                log.exception("fonte %s falhou para %s", getattr(fonte, "id", fonte), entrada.id)
                continue
            for chave, valor in (dados or {}).items():
                if valor and not reunido.get(chave):
                    reunido[chave] = valor
        return reunido

    # ------------------------------------------------------------------ mídia
    def _ler_asset(self, entrada: GameCatalogEntry, base: str) -> tuple[str, bytes] | None:
        """Lê ``logo.*``/``banner.*`` da pasta ``assets/`` do provider, se houver.

        Devolve (nome do arquivo, conteúdo) ou ``None`` — o que faz o download
        da internet continuar valendo para quem não deixou imagem local.
        """
        provider = self._providers.get(entrada.provider_id)
        pasta = self._assets_dir(provider) if provider is not None else None
        if pasta is None:
            return None
        try:
            if not pasta.is_dir():
                return None
            for arq in pasta.iterdir():
                nome = arq.name.lower()
                if arq.is_file() and nome.rsplit(".", 1)[0] == base and nome.endswith(ASSET_EXTS):
                    return arq.name, arq.read_bytes()
        except (FileNotFoundError, NotADirectoryError, OSError):
            return None
        return None

    def _localizar_assets(self, entrada: GameCatalogEntry, extra: dict) -> dict:
        """Copia as imagens locais do provider para a pasta de mídia e aponta as
        URLs para elas. Sem imagem local, não mexe em nada."""
        dados = dict(extra or {})
        for campo, base in (("banner_url", "banner"), ("logo_url", "logo")):
            achado = self._ler_asset(entrada, base)
            if achado is None:
                continue
            arqnome, conteudo = achado
            ext = "." + arqnome.rsplit(".", 1)[-1].lower()
            nome = f"{entrada.id}-{base}-{hashlib.sha1(conteudo).hexdigest()[:10]}{ext}"
            destino = self.media_dir / nome
            try:
                if not destino.is_file():
                    self.media_dir.mkdir(parents=True, exist_ok=True)
                    destino.write_bytes(conteudo)
                dados[campo] = f"{PREFIXO_MEDIA}{entrada.id}/media/{nome}"
            except OSError as exc:
                log.info("não foi possível gravar o asset %s de %s: %s", base, entrada.id, exc)
        return dados

    async def _localizar_imagens(self, final: GameCatalogEntry, extra: dict) -> dict:
        """Traz banner e logo para o disco e troca a URL pela nossa.

        Sem isso a página depende de uma CDN de terceiro a cada visita — e some
        numa rede fechada, que é justamente onde muitos servidores vivem.
        """
        dados = dict(extra or {})
        if self._baixar is None:
            return dados
        game_id = final.id
        for campo in IMAGENS:
            url = getattr(final, campo, "")
            if not url or not str(url).startswith("http"):
                continue
            try:
                # A extensão vem da URL: nem toda fonte serve JPEG — o logo do
                # Minecraft é SVG, e servir tudo como image/jpeg quebra a imagem.
                sufixo = Path(str(url).split("?")[0]).suffix.lower()
                if sufixo not in (".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"):
                    sufixo = ".jpg"
                nome = (
                    f"{game_id}-{campo[:6]}-{hashlib.sha1(url.encode()).hexdigest()[:10]}{sufixo}"
                )
                destino = self.media_dir / nome
                if not destino.is_file():
                    self.media_dir.mkdir(parents=True, exist_ok=True)
                    conteudo = await self._baixar(url)
                    await asyncio.to_thread(destino.write_bytes, conteudo)
                dados[campo] = f"{PREFIXO_MEDIA}{game_id}/media/{nome}"
            except Exception as exc:  # noqa: BLE001 - imagem é enfeite, não bloqueia
                log.info("não foi possível baixar %s de %s: %s", campo, game_id, exc)
        return dados

    TIPOS = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
    }

    def media_path(self, game_id: str, arquivo: str) -> tuple[Path, str]:
        """Caminho e tipo do arquivo. O tipo sai da extensão, porque servir um
        SVG como image/jpeg faz o navegador desenhar nada."""
        # Só o nome do arquivo: nome com ../ não pode escapar da pasta de mídia.
        alvo = self.media_dir / Path(arquivo).name
        if not alvo.is_file():
            raise NotFoundError(f"imagem não encontrada: {arquivo}")
        return alvo, self.TIPOS.get(alvo.suffix.lower(), "application/octet-stream")

    # ------------------------------------------------------------------ cache
    def _arquivo(self, game_id: str) -> Path:
        return self._dir / f"{game_id}.json"

    def _ler_cache(self, game_id: str) -> dict | None:
        arquivo = self._arquivo(game_id)
        try:
            bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - bruto.get("buscado_em", 0) > TTL_SEGUNDOS:
            return None
        return bruto.get("dados") or {}

    def _gravar_cache(self, game_id: str, dados: dict) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._arquivo(game_id).write_text(
                json.dumps(
                    {"buscado_em": time.time(), "dados": dados},
                    ensure_ascii=False,
                    default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            log.info("não foi possível gravar o cache do catálogo: %s", exc)
