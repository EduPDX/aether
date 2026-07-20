"""Lixeira: item apagado, com a origem preservada para poder voltar.

O ponto de existir uma entidade aqui — em vez de só mover o arquivo para uma
pasta — é o campo `original_path`. A primeira versão da lixeira guardava apenas
o nome do arquivo, e por isso restaurar era impossível: sabia-se *o que* tinha
sido apagado, nunca *de onde*.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

# Quanto tempo um item fica antes da limpeza automática, e o teto de espaço.
# Sem os dois, a pasta cresce para sempre — foi o que aconteceu na prática.
RETENCAO_DIAS = 30
TETO_BYTES = 2 * 1024**3

_SEGURO = re.compile(r"[^A-Za-z0-9._-]+")


class TrashOrigin(StrEnum):
    """De qual tela o item saiu.

    Importa na restauração: `FILES` volta para um caminho relativo à raiz da
    instância, `CONTENT` volta para a pasta do tipo de conteúdo (mods, etc).
    """

    FILES = "files"
    CONTENT = "content"


@dataclass(frozen=True)
class TrashItem:
    id: str
    instance_id: str
    original_path: str
    stored_name: str
    is_dir: bool
    size_bytes: int
    origin: TrashOrigin
    content_type: str = ""
    trashed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(
        instance_id: str,
        original_path: str,
        stored_name: str,
        *,
        is_dir: bool,
        size_bytes: int,
        origin: TrashOrigin,
        content_type: str = "",
    ) -> "TrashItem":
        return TrashItem(
            id=uuid.uuid4().hex,
            instance_id=instance_id,
            original_path=original_path,
            stored_name=stored_name,
            is_dir=is_dir,
            size_bytes=size_bytes,
            origin=origin,
            content_type=content_type,
        )

    @property
    def name(self) -> str:
        """Nome original, que é o que a pessoa reconhece.

        `stored_name` pode ter sufixo de desambiguação — dois arquivos com o
        mesmo nome apagados em momentos diferentes convivem na mesma pasta.
        """
        return self.original_path.rsplit("/", 1)[-1]


def stored_name_for(item_name: str, token: str) -> str:
    """Nome do item dentro da pasta da lixeira.

    O token evita a colisão que a versão anterior resolvia acrescentando `.1`
    ao final — o que estragava a extensão e, com ela, a chance de restaurar o
    arquivo com o nome certo.
    """
    limpo = _SEGURO.sub("-", item_name).strip("-") or "item"
    sufixo = _SEGURO.sub("", token)[:8] or uuid.uuid4().hex[:8]
    return f"{sufixo}_{limpo}"


def select_for_pruning(
    items: list[TrashItem],
    now: datetime,
    *,
    dias: int = RETENCAO_DIAS,
    teto: int = TETO_BYTES,
) -> list[TrashItem]:
    """Itens que a limpeza automática deve remover.

    Duas regras somadas: vence por idade, ou cede espaço para caber no teto.
    A segunda apaga do mais antigo para o mais novo — quem apagou algo há dez
    minutos tem muito mais chance de querer de volta do que quem apagou no mês
    passado.
    """
    vencidos = {i.id for i in items if now - i.trashed_at > timedelta(days=dias)}

    restantes = sorted((i for i in items if i.id not in vencidos), key=lambda i: i.trashed_at)
    total = sum(i.size_bytes for i in restantes)
    excedentes: set[str] = set()
    for item in restantes:
        if total <= teto:
            break
        excedentes.add(item.id)
        total -= item.size_bytes

    alvos = vencidos | excedentes
    return [i for i in items if i.id in alvos]
