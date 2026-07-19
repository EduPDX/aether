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
    ) -> list[SourceItem]:
        fonte = self._source(instance, source_id)
        versao, loader = self._game_context(instance) if filter_by_game else (None, None)
        return await fonte.search(
            query, game_version=versao, loader=loader, limit=limit, offset=offset
        )

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
        obter = getattr(fonte, "version_by_id", None)
        if callable(obter):
            versao = await obter(version_id)
        else:
            versao = None
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
