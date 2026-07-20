"""Contrato de gerenciamento de jogadores.

Quem são os jogadores, como são identificados e onde ficam as listas de acesso
é conhecimento do jogo. O Core sabe *quando* aplicar cada mudança — pelo
console, com o servidor de pé, ou direto no arquivo, com ele parado — e é essa
decisão que evita a classe de bug mais chata desta área.

Só o provider de Minecraft implementa isto hoje. O contrato existe para que o
próximo jogo se encaixe implementando um protocolo, em vez de forçar uma
refatoração do Core e do dashboard.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable


class PlayerListKind(StrEnum):
    """Categorias que praticamente todo servidor de jogo tem, com nomes
    diferentes: liberados, quem manda, e quem não entra."""

    ALLOW = "allow"
    ADMIN = "admin"
    BANNED = "banned"


class PlayerAction(StrEnum):
    ALLOW_ADD = "allow_add"
    ALLOW_REMOVE = "allow_remove"
    ADMIN_ADD = "admin_add"
    ADMIN_REMOVE = "admin_remove"
    BAN = "ban"
    UNBAN = "unban"
    KICK = "kick"


#: Ações que só fazem sentido com o servidor no ar — não há o que escrever em
#: disco para expulsar alguém que já está conectado.
LIVE_ONLY = frozenset({PlayerAction.KICK})


@dataclass(frozen=True)
class PlayerEntry:
    """Um jogador dentro de uma lista.

    `id` é o identificador estável do jogo (UUID no Minecraft) e pode vir
    vazio: nem todo jogo tem um, e nem toda lista o exige.
    """

    name: str
    id: str = ""
    #: Texto livre mostrado ao lado do nome — motivo do banimento, nível do
    #: operador, data. O Core não interpreta.
    detail: str = ""


@dataclass(frozen=True)
class PlayerList:
    kind: PlayerListKind
    #: Nome que o jogo dá a esta lista, para a interface não inventar jargão.
    label: str
    entries: tuple[PlayerEntry, ...] = field(default_factory=tuple)
    #: Falso quando o recurso existe mas está desligado na configuração — no
    #: Minecraft, `white-list=false`. A interface avisa em vez de deixar o
    #: usuário editar uma lista que o servidor ignora.
    enforced: bool = True


@runtime_checkable
class SupportsPlayers(Protocol):
    """Provider que sabe ler e alterar as listas de acesso do seu jogo."""

    def player_lists(self, root: Path) -> list[PlayerList]:
        """Lê as listas do disco."""
        ...

    def player_command(self, action: PlayerAction, name: str, reason: str = "") -> str | None:
        """Comando de console equivalente à ação, ou None se não houver.

        É o caminho preferido quando o servidor está rodando: quem edita as
        listas é o próprio servidor, então não há divergência entre o que está
        em memória e o que está em disco.
        """
        ...

    def apply_player_action(
        self, root: Path, action: PlayerAction, name: str, reason: str = ""
    ) -> None:
        """Aplica a ação nos arquivos, para quando o servidor está parado.

        Não deve ser chamado com o servidor no ar: as listas vivem em memória e
        seriam reescritas por cima, descartando a alteração em silêncio.
        """
        ...
