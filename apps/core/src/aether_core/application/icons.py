"""Ícone do servidor — o PNG que aparece na lista de servidores do jogo.

O redimensionamento acontece no navegador, que já sabe decodificar e reescalar
imagem via canvas. O Core só valida e grava: assim não entra uma dependência
de processamento de imagem no servidor para resolver algo que o cliente já faz.
"""

import asyncio
import struct
from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.domain.errors import NotFoundError, ValidationFailedError
from aether_core.domain.instances import Instance

# O Minecraft exige exatamente isto; qualquer outra coisa e o servidor ignora
# o arquivo silenciosamente.
ICON_FILE = "server-icon.png"
ICON_SIZE = 64
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
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def _path(self, instance: Instance) -> Path:
        return Path(instance.root_dir) / ICON_FILE

    def exists(self, instance: Instance) -> bool:
        return self._path(instance).is_file()

    def resolve(self, instance: Instance) -> Path:
        caminho = self._path(instance)
        if not caminho.is_file():
            raise NotFoundError("esta instância não tem ícone")
        return caminho

    async def save(self, instance: Instance, data: bytes) -> dict:
        if len(data) > _TAMANHO_MAX:
            raise ValidationFailedError("o ícone passa de 512 KB")
        largura, altura = png_dimensions(data)
        if (largura, altura) != (ICON_SIZE, ICON_SIZE):
            raise ValidationFailedError(
                f"o ícone precisa ser {ICON_SIZE}x{ICON_SIZE}; este é {largura}x{altura}"
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
        return {"file": ICON_FILE, "size": len(data)}

    async def delete(self, instance: Instance) -> None:
        caminho = self._path(instance)
        await asyncio.to_thread(caminho.unlink, True)
        await self._bus.publish("instance.icon_changed", {"instance_id": instance.id})
