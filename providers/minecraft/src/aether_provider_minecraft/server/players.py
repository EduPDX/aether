"""Listas de acesso do Minecraft: whitelist, operadores e banimentos.

Cada lista é um JSON na raiz do servidor. O formato é estável há muitas versões
e é o mesmo que o servidor escreve, então o que gravamos aqui ele lê de volta
sem conversão.
"""

import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from aether_sdk import PlayerAction, PlayerEntry, PlayerList, PlayerListKind

WHITELIST = "whitelist.json"
OPS = "ops.json"
BANNED = "banned-players.json"

#: O servidor recusa nomes fora disto, então recusar antes evita gravar lixo
#: numa lista que o Minecraft depois ignora em silêncio.
NOME_VALIDO = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def offline_uuid(name: str) -> str:
    """UUID que o Minecraft atribui a um jogador quando `online-mode=false`.

    É determinístico — hash do nome — e não depende da Mojang, o que permite
    liberar alguém que nunca entrou no servidor. Conferido contra os UUIDs
    reais de um servidor em produção.

    Com `online-mode=true` isto NÃO vale: lá o UUID vem da conta Mojang, e
    inventar um faria a entrada nunca casar com o jogador de verdade.
    """
    b = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode()).digest())
    b[6] = (b[6] & 0x0F) | 0x30  # versão 3
    b[8] = (b[8] & 0x3F) | 0x80  # variante RFC 4122
    return str(uuid.UUID(bytes=bytes(b)))


def _ler(root: Path, arquivo: str) -> list[dict]:
    caminho = root / arquivo
    if not caminho.is_file():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8") or "[]")
    except (json.JSONDecodeError, OSError):
        # Arquivo corrompido não pode derrubar a tela inteira; some da lista e
        # o usuário vê a lista vazia em vez de um erro no dashboard.
        return []
    return dados if isinstance(dados, list) else []


def _gravar(root: Path, arquivo: str, dados: list[dict]) -> None:
    caminho = root / arquivo
    # Escreve ao lado e troca: se faltar energia no meio, o arquivo antigo
    # continua íntegro em vez de virar um JSON pela metade.
    parcial = caminho.with_suffix(caminho.suffix + ".parcial")
    parcial.write_text(json.dumps(dados, indent=2), encoding="utf-8", newline="\n")
    parcial.replace(caminho)


def _propriedade(root: Path, chave: str, padrao: str = "") -> str:
    arq = root / "server.properties"
    if not arq.is_file():
        return padrao
    for linha in arq.read_text(encoding="utf-8", errors="replace").splitlines():
        if linha.startswith(f"{chave}="):
            return linha.split("=", 1)[1].strip()
    return padrao


def player_lists(root: Path) -> list[PlayerList]:
    permitidos = [
        PlayerEntry(name=e.get("name", ""), id=e.get("uuid", "")) for e in _ler(root, WHITELIST)
    ]

    operadores = []
    for e in _ler(root, OPS):
        nivel = e.get("level", 4)
        operadores.append(
            PlayerEntry(name=e.get("name", ""), id=e.get("uuid", ""), detail=f"nível {nivel}")
        )

    banidos = []
    for e in _ler(root, BANNED):
        motivo = e.get("reason") or "sem motivo registrado"
        quando = (e.get("created") or "")[:10]
        banidos.append(
            PlayerEntry(
                name=e.get("name", ""),
                id=e.get("uuid", ""),
                detail=f"{motivo} — {quando}" if quando else motivo,
            )
        )

    # `white-list=false` faz o servidor ignorar a lista por completo. Sem este
    # aviso o usuário adiciona gente e não entende por que estranhos entram.
    ativa = _propriedade(root, "white-list", "false").lower() == "true"

    return [
        PlayerList(
            kind=PlayerListKind.ALLOW,
            label="Whitelist",
            entries=tuple(permitidos),
            enforced=ativa,
        ),
        PlayerList(kind=PlayerListKind.ADMIN, label="Operadores", entries=tuple(operadores)),
        PlayerList(kind=PlayerListKind.BANNED, label="Banidos", entries=tuple(banidos)),
    ]


def player_command(action: PlayerAction, name: str, reason: str = "") -> str | None:
    """Comando de console equivalente à ação."""
    motivo = f" {reason}".rstrip() if reason else ""
    return {
        PlayerAction.ALLOW_ADD: f"whitelist add {name}",
        PlayerAction.ALLOW_REMOVE: f"whitelist remove {name}",
        PlayerAction.ADMIN_ADD: f"op {name}",
        PlayerAction.ADMIN_REMOVE: f"deop {name}",
        PlayerAction.BAN: f"ban {name}{motivo}",
        PlayerAction.UNBAN: f"pardon {name}",
        PlayerAction.KICK: f"kick {name}{motivo}",
    }.get(action)


def apply_player_action(root: Path, action: PlayerAction, name: str, reason: str = "") -> None:
    """Aplica direto nos arquivos — só com o servidor parado."""
    if action is PlayerAction.KICK:
        raise ValueError("kick exige o servidor rodando")

    uid = _uuid_de(root, name)

    if action is PlayerAction.ALLOW_ADD:
        _adicionar(root, WHITELIST, {"uuid": uid, "name": name})
    elif action is PlayerAction.ALLOW_REMOVE:
        _remover(root, WHITELIST, name)
    elif action is PlayerAction.ADMIN_ADD:
        _adicionar(root, OPS, {"uuid": uid, "name": name, "level": 4, "bypassesPlayerLimit": False})
    elif action is PlayerAction.ADMIN_REMOVE:
        _remover(root, OPS, name)
    elif action is PlayerAction.BAN:
        _adicionar(
            root,
            BANNED,
            {
                "uuid": uid,
                "name": name,
                "created": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
                "source": "Aether",
                "expires": "forever",
                "reason": reason or "Banned by an operator.",
            },
        )
        # Banir alguém que continua na whitelist é contraditório: some da
        # whitelist junto, que é o que o próprio servidor faz.
        _remover(root, WHITELIST, name)
    elif action is PlayerAction.UNBAN:
        _remover(root, BANNED, name)


def _uuid_de(root: Path, name: str) -> str:
    """UUID do jogador: do cache do servidor, senão calculado.

    O usercache tem o UUID verdadeiro de quem já entrou — inclusive em
    `online-mode=true`, onde calcular não funcionaria.
    """
    for e in _ler(root, "usercache.json"):
        if e.get("name", "").lower() == name.lower():
            return e.get("uuid", "")

    if _propriedade(root, "online-mode", "true").lower() == "true":
        raise ValueError(
            f"{name} nunca entrou neste servidor e o modo online está ligado, "
            "então o UUID precisa vir da Mojang. Inicie o servidor e refaça — "
            "assim ele resolve o nome sozinho."
        )
    return offline_uuid(name)


def _adicionar(root: Path, arquivo: str, entrada: dict) -> None:
    dados = _ler(root, arquivo)
    nome = entrada["name"].lower()
    if any(e.get("name", "").lower() == nome for e in dados):
        return  # já está lá; repetir criaria entrada duplicada
    dados.append(entrada)
    _gravar(root, arquivo, dados)


def _remover(root: Path, arquivo: str, name: str) -> None:
    dados = _ler(root, arquivo)
    restante = [e for e in dados if e.get("name", "").lower() != name.lower()]
    if len(restante) != len(dados):
        _gravar(root, arquivo, restante)
