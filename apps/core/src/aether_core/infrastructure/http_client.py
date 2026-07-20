"""Cliente HTTP para os catálogos externos.

Fica na infraestrutura porque é detalhe de transporte: o provider recebe as
funções e o serviço não sabe que existe httpx.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Catálogos pedem identificação; sem isso o Modrinth pode limitar mais cedo.
USER_AGENT = "Aether/0.1 (+https://github.com/EduPDX/aether)"
TIMEOUT = httpx.Timeout(15.0, connect=8.0, read=30.0)


class CatalogHttp:
    """GET/POST em JSON com tratamento de 404 como "não achou"."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            )
        return self._client

    async def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        res = await self._get_client().get(url, params=params)
        # 404 é resposta legítima: hash desconhecido, projeto inexistente.
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def post(self, url: str, json: dict[str, Any]) -> Any:
        res = await self._get_client().post(url, json=json)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


class HttpDownloader:
    """Baixa arquivos em blocos, sem carregar tudo em memória."""

    def __init__(self, chunk: int = 1 << 18) -> None:
        self._chunk = chunk

    def stream(self, url: str) -> AsyncIterator[bytes]:
        async def gen() -> AsyncIterator[bytes]:
            async with (
                httpx.AsyncClient(
                    timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
                ) as client,
                client.stream("GET", url) as res,
            ):
                res.raise_for_status()
                async for bloco in res.aiter_bytes(self._chunk):
                    yield bloco

        return gen()
