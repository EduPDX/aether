"""Ícone do servidor — o PNG que aparece na lista de servidores do jogo.

O redimensionamento acontece no navegador, que já sabe decodificar e reescalar
imagem via canvas. O Core só valida e grava: assim não entra uma dependência
de processamento de imagem no servidor para resolver algo que o cliente já faz.
"""

import asyncio
import struct
from pathlib import Path

from aether_sdk import IconSpec

from aether_core.application.events import EventBus
from aether_core.application.ports import ProviderRegistry
from aether_core.domain.errors import NotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_TAMANHO_MAX = 512 * 1024


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Largura e altura lidas do cabeçalho IHDR.

    Ler os 24 primeiros bytes evita decodificar a imagem inteira só para
    saber o tamanho — e é tudo que a validação precisa.
    """
    if not data.startswith(_PNG_MAGIC):
        raise ValidationFailedError("o arquivo não é um PNG")
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValidationFailedError("PNG malformado: cabeçalho IHDR ausente")
    largura, altura = struct.unpack(">II", data[16:24])
    return largura, altura


class ServerIconService:
    """A regra do ícone (nome do arquivo, dimensão) vem do manifest do
    provider — cada jogo declara a sua; o Core só valida e grava."""

    def __init__(self, bus: EventBus, providers: ProviderRegistry) -> None:
        self._bus = bus
        self._providers = providers

    def _spec(self, instance: Instance) -> IconSpec:
        spec = self._providers.get(instance.provider_id).manifest.icon_spec
        if spec is None:
            raise ValidationFailedError("este jogo não usa ícone de servidor")
        return spec

    def _path(self, instance: Instance) -> Path:
        return Path(instance.root_dir) / self._spec(instance).file

    def exists(self, instance: Instance) -> bool:
        return self._path(instance).is_file()

    def resolve(self, instance: Instance) -> Path:
        caminho = self._path(instance)
        if not caminho.is_file():
            raise NotFoundError("esta instância não tem ícone")
        return caminho

    async def save(self, instance: Instance, data: bytes) -> dict:
        spec = self._spec(instance)
        if len(data) > _TAMANHO_MAX:
            raise ValidationFailedError("o ícone passa de 512 KB")
        largura, altura = png_dimensions(data)
        if (largura, altura) != (spec.size, spec.size):
            raise ValidationFailedError(
                f"o ícone precisa ser {spec.size}x{spec.size}; este é {largura}x{altura}"
            )
        raiz = Path(instance.root_dir)
        if not raiz.is_dir():
            raise NotFoundError(f"raiz da instância não encontrada: {raiz}")

        destino = self._path(instance)
        # Grava por arquivo temporário: um upload interrompido não pode deixar
        # um PNG truncado que o servidor tentaria carregar.
        parcial = destino.with_suffix(".png.parcial")
        try:
            await asyncio.to_thread(parcial.write_bytes, data)
            await asyncio.to_thread(parcial.replace, destino)
        except Exception:
            parcial.unlink(missing_ok=True)
            raise

        await self._bus.publish("instance.icon_changed", {"instance_id": instance.id})
        return {"file": spec.file, "size": len(data)}

    async def delete(self, instance: Instance) -> None:
        caminho = self._path(instance)
        await asyncio.to_thread(caminho.unlink, True)
        await self._bus.publish("instance.icon_changed", {"instance_id": instance.id})
