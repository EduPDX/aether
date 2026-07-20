"""Casos de uso de catálogo: buscar, instalar e detectar atualizações."""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aether_sdk import ContentSource, SourceItem, SourceVersion

from aether_core.application.events import EventBus
from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from aether_core.domain.instances import Instance

# Baixar em blocos: um mod pode ter dezenas de MB e não deve virar um bytes()
# inteiro em memória.
_BLOCO = 1 << 18


class Downloader(Protocol):
    def stream(self, url: str) -> AsyncIterator[bytes]: ...


@dataclass(frozen=True)
class PlannedItem:
    project_id: str
    version_id: str
    version_number: str
    file_name: str
    size: int
    """Quem exigiu este item: None = foi o que o usuário pediu."""
    required_by: str | None = None


@dataclass(frozen=True)
class InstallPlan:
    """O que uma instalação vai fazer, calculado antes de tocar no disco.

    Existe para a instalação não ser uma cascata cega: se a terceira
    dependência não tiver versão compatível, é melhor descobrir antes de já
    ter escrito as duas primeiras na pasta de mods.
    """

    items: list[PlannedItem]
    already_installed: list[str]
    """Dependências obrigatórias sem versão compatível — impedem o plano."""
    missing: list[str]
    """Mods instalados que a nova versão declara incompatíveis."""
    conflicts: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing

    @property
    def total_size(self) -> int:
        return sum(i.size for i in self.items)


# Um grafo de dependências mal formado não pode virar recursão infinita nem
# baixar meia internet; profundidade é suficiente para os casos reais.
_PROFUNDIDADE_MAX = 6


@dataclass(frozen=True)
class UpdateCandidate:
    """Um mod instalado que tem versão mais nova no catálogo."""

    file: str
    project_id: str
    source_id: str
    display_name: str
    current_version: str
    latest_version: str
    latest_version_id: str
    latest_file_name: str
    released_at: str | None


class SourceService:
    def __init__(
        self,
        providers: ProviderRegistry,
        downloader: Downloader,
        bus: EventBus,
        content_dir_of,
    ) -> None:
        self._providers = providers
        self._downloader = downloader
        self._bus = bus
        # Injetado para não duplicar a resolução de diretório do ContentService.
        self._content_dir_of = content_dir_of

    # ---------------------------------------------------------------- fontes
    def sources(self, instance: Instance) -> list[ContentSource]:
        provider = self._providers.get(instance.provider_id)
        obter = getattr(provider, "content_sources", None)
        return list(obter()) if callable(obter) else []

    def _source(self, instance: Instance, source_id: str) -> ContentSource:
        for fonte in self.sources(instance):
            if fonte.id == source_id:
                return fonte
        raise NotFoundError(f"catálogo desconhecido: {source_id}")

    def _game_context(self, instance: Instance) -> tuple[str | None, str | None]:
        """Versão do jogo e loader detectados, para filtrar a busca.

        Sem isso a busca devolve mods de qualquer versão e o usuário instala
        algo que não carrega.
        """
        dados = instance.provider_data or {}
        return dados.get("game_version"), dados.get("loader")

    # ----------------------------------------------------------------- busca
    async def search(
        self,
        instance: Instance,
        source_id: str,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        filter_by_game: bool = True,
        categories: tuple[str, ...] = (),
        loader_override: str | None = None,
    ) -> list[SourceItem]:
        fonte = self._source(instance, source_id)
        versao, loader = self._game_context(instance) if filter_by_game else (None, None)
        return await fonte.search(
            query,
            game_version=versao,
            loader=loader_override or loader,
            categories=categories,
            limit=limit,
            offset=offset,
        )

    def filters(self, instance: Instance, source_id: str) -> dict:
        """Filtros que este catálogo oferece, para a interface montar sozinha."""
        fonte = self._source(instance, source_id)
        cats = getattr(fonte, "available_categories", None)
        loaders = getattr(fonte, "available_loaders", None)
        return {
            "categories": [{"id": i, "label": r} for i, r in (cats() if callable(cats) else ())],
            "loaders": [{"id": i, "label": r} for i, r in (loaders() if callable(loaders) else ())],
        }

    async def versions(
        self, instance: Instance, source_id: str, project_id: str, *, filter_by_game: bool = True
    ) -> list[SourceVersion]:
        fonte = self._source(instance, source_id)
        versao, loader = self._game_context(instance) if filter_by_game else (None, None)
        return await fonte.versions(project_id, game_version=versao, loader=loader)

    # ------------------------------------------------------------- instalação
    async def install(
        self,
        instance: Instance,
        ctype_id: str,
        version: SourceVersion,
        *,
        overwrite: bool = False,
    ) -> dict:
        if not version.download_url or not version.file_name:
            raise ValidationFailedError("esta versão não publica um arquivo para baixar")

        pasta = Path(self._content_dir_of(instance, ctype_id))
        pasta.mkdir(parents=True, exist_ok=True)
        # basename: o nome vem do catálogo, que é externo — não pode escapar.
        nome = Path(version.file_name).name
        destino = pasta / nome
        if destino.exists() and not overwrite:
            raise ConflictError(f"já existe: {nome}")

        parcial = destino.with_suffix(destino.suffix + ".parcial")
        sha1 = hashlib.sha1()
        sha512 = hashlib.sha512()
        total = 0
        try:
            with open(parcial, "wb") as saida:
                async for bloco in self._downloader.stream(version.download_url):
                    saida.write(bloco)
                    sha1.update(bloco)
                    sha512.update(bloco)
                    total += len(bloco)

            # Integridade: o arquivo vem de fora e vai ser executado pelo
            # servidor. Sem conferir, um download truncado ou adulterado entra
            # na pasta de mods como se estivesse certo.
            if version.sha1 and sha1.hexdigest() != version.sha1:
                raise ValidationFailedError(
                    f"sha1 não confere para {nome}: o download está corrompido"
                )
            if version.sha512 and sha512.hexdigest() != version.sha512:
                raise ValidationFailedError(
                    f"sha512 não confere para {nome}: o download está corrompido"
                )
            if version.size and total != version.size:
                raise ValidationFailedError(
                    f"tamanho não confere para {nome}: {total} bytes, esperado {version.size}"
                )

            parcial.replace(destino)
        except Exception:
            parcial.unlink(missing_ok=True)  # nunca deixa .parcial para trás
            raise

        await self._bus.publish(
            "content.installed",
            {
                "instance_id": instance.id,
                "file": nome,
                "source": version.source_id,
                "version": version.version_number,
            },
        )
        return {"file": nome, "size": total, "version": version.version_number}

    # ----------------------------------------------------------- dependências
    async def _installed_project_ids(
        self, instance: Instance, ctype_id: str, fonte: ContentSource
    ) -> set[str]:
        """Projetos já presentes na pasta, identificados por hash."""
        pasta = Path(self._content_dir_of(instance, ctype_id))
        if not pasta.is_dir():
            return set()
        arquivos = [p for p in pasta.iterdir() if p.is_file() and p.suffix == ".jar"]
        if not arquivos:
            return set()
        hashes = await asyncio.gather(*(asyncio.to_thread(_sha1, p) for p in arquivos))
        encontrados = await self._lookup(fonte, list(hashes))
        return {v.project_id for v in encontrados.values() if v.project_id}

    async def plan_install(
        self,
        instance: Instance,
        ctype_id: str,
        source_id: str,
        version_id: str,
    ) -> InstallPlan:
        """Monta a árvore de dependências obrigatórias sem instalar nada.

        Resolver em cascata direto no disco deixaria um conjunto meio
        instalado quando uma dependência no meio do caminho não tem versão
        compatível. Aqui o problema aparece antes de o primeiro byte ser
        escrito.
        """
        fonte = self._source(instance, source_id)
        raiz = await self._version_by_id(fonte, version_id)
        if raiz is None:
            raise NotFoundError(f"versão não encontrada: {version_id}")

        instalados = await self._installed_project_ids(instance, ctype_id, fonte)
        versao_jogo, loader = self._game_context(instance)

        itens: list[PlannedItem] = []
        ja_tem: list[str] = []
        faltando: list[str] = []
        conflitos: list[str] = []
        # Guarda o que já entrou no plano: um grafo com ciclo (A→B→A) ou um
        # diamante (dois mods pedindo a mesma lib) não pode duplicar nem travar.
        vistos: set[str] = {raiz.project_id}

        async def visitar(versao: SourceVersion, quem: str | None, profundidade: int) -> None:
            itens.append(
                PlannedItem(
                    project_id=versao.project_id,
                    version_id=versao.version_id,
                    version_number=versao.version_number,
                    file_name=versao.file_name,
                    size=versao.size,
                    required_by=quem,
                )
            )
            if profundidade >= _PROFUNDIDADE_MAX:
                return

            for dep in versao.dependencies:
                if dep.kind == "incompatible":
                    if dep.project_id in instalados:
                        conflitos.append(dep.project_id)
                    continue
                # Opcionais e embutidas não entram: embutidas já vêm dentro do
                # jar, e opcionais são escolha do usuário, não requisito.
                if dep.kind != "required":
                    continue
                if dep.project_id in instalados:
                    ja_tem.append(dep.project_id)
                    continue
                if dep.project_id in vistos:
                    continue
                vistos.add(dep.project_id)

                try:
                    disponiveis = await fonte.versions(
                        dep.project_id, game_version=versao_jogo, loader=loader
                    )
                except Exception:
                    disponiveis = []
                if not disponiveis:
                    faltando.append(dep.project_id)
                    continue
                quem_pediu = versao.file_name or versao.project_id
                await visitar(disponiveis[0], quem_pediu, profundidade + 1)

        await visitar(raiz, None, 0)
        # Dependências primeiro: se algo falhar no meio, o que já entrou é o
        # que o resto precisa, não um mod solto sem suas libs.
        itens.reverse()
        return InstallPlan(
            items=itens,
            already_installed=sorted(set(ja_tem)),
            missing=sorted(set(faltando)),
            conflicts=sorted(set(conflitos)),
        )

    async def install_plan(
        self,
        instance: Instance,
        ctype_id: str,
        source_id: str,
        plan: InstallPlan,
        *,
        overwrite: bool = False,
    ) -> dict:
        """Executa um plano já validado."""
        if not plan.ok:
            raise ValidationFailedError(
                "o plano tem dependências obrigatórias sem versão compatível: "
                + ", ".join(plan.missing)
            )
        fonte = self._source(instance, source_id)
        instalados: list[dict] = []
        for item in plan.items:
            versao = await self._version_by_id(fonte, item.version_id)
            if versao is None:
                continue
            try:
                instalados.append(
                    await self.install(instance, ctype_id, versao, overwrite=overwrite)
                )
            except ConflictError:
                # Já estava lá: não é falha do plano.
                continue
        return {"installed": instalados, "count": len(instalados)}

    @staticmethod
    async def _version_by_id(fonte: ContentSource, version_id: str) -> SourceVersion | None:
        obter = getattr(fonte, "version_by_id", None)
        return await obter(version_id) if callable(obter) else None

    async def install_by_id(
        self,
        instance: Instance,
        ctype_id: str,
        source_id: str,
        version_id: str,
        *,
        overwrite: bool = False,
    ) -> dict:
        fonte = self._source(instance, source_id)
        versao = await self._version_by_id(fonte, version_id)
        if versao is None:
            raise NotFoundError(f"versão não encontrada: {version_id}")
        return await self.install(instance, ctype_id, versao, overwrite=overwrite)

    # ------------------------------------------------------------ atualizações
    async def check_updates(
        self, instance: Instance, ctype_id: str, source_id: str
    ) -> list[UpdateCandidate]:
        """Compara o que está instalado com o mais recente do catálogo.

        Identifica por hash, não por nome de arquivo: o usuário pode ter
        renomeado o .jar, e o nome não diz a versão de forma confiável.
        """
        fonte = self._source(instance, source_id)
        pasta = Path(self._content_dir_of(instance, ctype_id))
        if not pasta.is_dir():
            return []

        arquivos = [p for p in sorted(pasta.iterdir()) if p.is_file() and p.suffix == ".jar"]
        hashes = await asyncio.gather(*(asyncio.to_thread(_sha1, p) for p in arquivos))
        por_hash = dict(zip(hashes, arquivos, strict=True))

        instaladas = await self._lookup(fonte, list(por_hash))
        versao_jogo, loader = self._game_context(instance)

        async def candidato(h: str, atual: SourceVersion) -> UpdateCandidate | None:
            disponiveis = await fonte.versions(
                atual.project_id, game_version=versao_jogo, loader=loader
            )
            if not disponiveis:
                return None
            nova = disponiveis[0]
            if nova.version_id == atual.version_id:
                return None
            return UpdateCandidate(
                file=por_hash[h].name,
                project_id=atual.project_id,
                source_id=fonte.id,
                display_name=atual.file_name or por_hash[h].name,
                current_version=atual.version_number,
                latest_version=nova.version_number,
                latest_version_id=nova.version_id,
                latest_file_name=nova.file_name,
                released_at=nova.released_at.isoformat() if nova.released_at else None,
            )

        resultados = await asyncio.gather(
            *(candidato(h, v) for h, v in instaladas.items()), return_exceptions=True
        )
        # Um projeto que falhou não pode esconder os outros que têm update.
        return [r for r in resultados if isinstance(r, UpdateCandidate)]

    @staticmethod
    async def _lookup(fonte: ContentSource, hashes: list[str]) -> dict[str, SourceVersion]:
        em_lote = getattr(fonte, "lookup_many", None)
        if callable(em_lote):
            return await em_lote(hashes)
        achados = await asyncio.gather(
            *(fonte.lookup_by_hash(h) for h in hashes), return_exceptions=True
        )
        return {h: v for h, v in zip(hashes, achados, strict=True) if isinstance(v, SourceVersion)}


def _sha1(caminho: Path) -> str:
    h = hashlib.sha1()
    with open(caminho, "rb") as f:
        while bloco := f.read(_BLOCO):
            h.update(bloco)
    return h.hexdigest()
