"""Backup contract — what a backup *is* is knowledge of the game, not the Core.

Minecraft guarda mundo, propriedades e listas de acesso; Valheim guarda `.db`
e `.fwl`; Factorio guarda um único save. O Core sabe compactar, agendar e
reter — o provider diz o que entra e como deixar o disco consistente antes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BackupSpec:
    """Conjunto de caminhos que compõem um backup.

    Os padrões são globs relativos à raiz da instância. `exclude` vence
    `include`, o que permite pegar uma pasta inteira e descartar o que é
    volumoso e reproduzível (logs, cache, jars baixáveis de novo).
    """

    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    """Frase curta mostrada na interface para o usuário saber o que leva."""
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.include:
            raise ValueError("um backup precisa incluir ao menos um caminho")


@dataclass(frozen=True)
class QuiescePlan:
    """Como deixar o estado em disco consistente enquanto se copia.

    Servidor rodando escreve o mundo enquanto o backup lê, o que produz
    arquivo rasgado. Quando o provider sabe pausar a escrita, informa aqui os
    comandos de console; o Core os envia antes e depois da cópia.
    """

    before: tuple[str, ...] = field(default_factory=tuple)
    after: tuple[str, ...] = field(default_factory=tuple)
    """Segundos a aguardar após `before` para a escrita pendente terminar."""
    settle_seconds: float = 2.0


@runtime_checkable
class SupportsBackup(Protocol):
    """Provider que sabe descrever seus próprios backups."""

    def backup_spec(self, root: Path) -> BackupSpec:
        """O que entra no backup desta instância.

        Recebe a raiz porque o conjunto pode depender de configuração — no
        Minecraft o nome do mundo vem de `level-name` em server.properties.
        """
        ...

    def quiesce_plan(self) -> QuiescePlan:
        """Comandos para pausar e retomar a escrita. Vazio = não suportado."""
        ...
