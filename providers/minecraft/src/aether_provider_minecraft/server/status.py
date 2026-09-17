"""Server List Ping (SLP) — consulta o status de um servidor Minecraft.

O mesmo protocolo da lista de servidores do jogo: um handshake TCP devolve a
contagem de jogadores e o MOTD. Como o Core roda junto do servidor (localhost),
esta é a fonte confiável de "jogadores online" tanto para o painel quanto para
o launcher. É puro protocolo — sem dependência externa.
"""

from __future__ import annotations

import json
import re
import socket
import struct
import time


def _write_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(sock: socket.socket) -> int:
    result = 0
    shift = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise ConnectionError("conexão fechada")
        result |= (b[0] & 0x7F) << shift
        if not b[0] & 0x80:
            return result
        shift += 7
        if shift >= 35:
            raise ValueError("VarInt longo demais")


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("conexão fechada")
        buf.extend(chunk)
    return bytes(buf)


def _packet(payload: bytes) -> bytes:
    return _write_varint(len(payload)) + payload


def _flatten_motd(desc) -> str:
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        text = str(desc.get("text", "") or "")
        for extra in desc.get("extra", []) or []:
            text += _flatten_motd(extra)
        return text
    return ""


def player_names(players: dict) -> dict:
    """SLP publica uma amostra; não inventa nomes quando ela está oculta."""
    online = int(players.get("online", 0) or 0)
    sample = players.get("sample")
    if not isinstance(sample, list):
        return {"names": [] if online == 0 else None, "names_complete": online == 0}
    names = sorted(
        {
            item["name"]
            for item in sample
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and re.fullmatch(r"[A-Za-z0-9_]{1,16}", item["name"])
        },
        key=str.casefold,
    )
    return {"names": names, "names_complete": len(names) == online}


def query_status(host: str, port: int, timeout: float = 2.5) -> dict | None:
    """Consulta o servidor via SLP. Devolve dict ou None se offline/inacessível.

    Retorno: ``{online, max, version, motd, latency_ms}``.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            handshake = (
                _write_varint(0x00)
                + _write_varint(767)
                + _write_varint(len(host.encode()))
                + host.encode()
                + struct.pack(">H", port)
                + _write_varint(1)
            )
            sock.sendall(_packet(handshake))
            sock.sendall(_packet(_write_varint(0x00)))  # status request

            _read_varint(sock)  # tamanho do pacote
            if _read_varint(sock) != 0x00:  # packet id
                return None
            jlen = _read_varint(sock)
            if jlen <= 0 or jlen > 5_000_000:
                return None
            data = json.loads(_read_exact(sock, jlen).decode("utf-8", "replace"))
            players = data.get("players") or {}

            start = time.monotonic()
            try:
                sock.sendall(_packet(_write_varint(0x01) + struct.pack(">q", 0x1234_5678)))
                _read_varint(sock)
                _read_varint(sock)
                _read_exact(sock, 8)
            except OSError:
                pass
            latency_ms = int((time.monotonic() - start) * 1000)

            return {
                "online": int(players.get("online", 0) or 0),
                "max": int(players.get("max", 0) or 0),
                **player_names(players),
                "version": str((data.get("version") or {}).get("name", "") or ""),
                "motd": _flatten_motd(data.get("description", "")),
                "latency_ms": latency_ms,
            }
    except (OSError, ValueError, json.JSONDecodeError):
        return None
