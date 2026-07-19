"""Ícone do servidor: validação do PNG 64x64 que o jogo exige."""

import struct
import zlib

from conftest import create_instance


def _png(largura: int, altura: int) -> bytes:
    """PNG mínimo válido com as dimensões pedidas."""
    def chunk(tipo: bytes, dados: bytes) -> bytes:
        return (
            struct.pack(">I", len(dados))
            + tipo
            + dados
            + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", largura, altura, 8, 6, 0, 0, 0)
    linha = b"\x00" + b"\xff\x00\x00\xff" * largura
    idat = zlib.compress(linha * altura)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def test_icon_roundtrip(client, mods_dir):
    iid = create_instance(client, mods_dir)
    assert client.get(f"/api/v1/instances/{iid}/config/icon").status_code == 404

    res = client.put(
        f"/api/v1/instances/{iid}/config/icon",
        files={"upload": ("qualquer-nome.png", _png(64, 64), "image/png")},
    )
    assert res.status_code == 200, res.text
    # o arquivo é gravado com o nome exato que o Minecraft procura
    assert res.json()["file"] == "server-icon.png"
    assert (mods_dir / "server-icon.png").is_file()

    baixado = client.get(f"/api/v1/instances/{iid}/config/icon")
    assert baixado.status_code == 200
    assert baixado.headers["content-type"] == "image/png"

    assert client.delete(f"/api/v1/instances/{iid}/config/icon").status_code == 204
    assert not (mods_dir / "server-icon.png").exists()


def test_wrong_size_is_rejected_with_the_actual_size(client, mods_dir):
    """O jogo ignora em silêncio um ícone fora de 64x64 — o erro tem que ser claro."""
    iid = create_instance(client, mods_dir)
    res = client.put(
        f"/api/v1/instances/{iid}/config/icon",
        files={"upload": ("grande.png", _png(128, 128), "image/png")},
    )
    assert res.status_code == 400
    assert "128x128" in res.json()["detail"]
    assert not (mods_dir / "server-icon.png").exists()


def test_non_png_is_rejected(client, mods_dir):
    iid = create_instance(client, mods_dir)
    res = client.put(
        f"/api/v1/instances/{iid}/config/icon",
        files={"upload": ("foto.jpg", b"\xff\xd8\xff\xe0 jpeg de verdade", "image/jpeg")},
    )
    assert res.status_code == 400
    assert "PNG" in res.json()["detail"]


def test_upload_does_not_leave_a_partial_file(client, mods_dir):
    iid = create_instance(client, mods_dir)
    client.put(
        f"/api/v1/instances/{iid}/config/icon",
        files={"upload": ("i.png", _png(64, 64), "image/png")},
    )
    assert not list(mods_dir.glob("*.parcial"))
