"""Remoção de instância: apagar de verdade o que era só daquele servidor.

A regra antiga era "remover instância nunca toca em arquivo", e ela nasceu
certa: quando toda instância era uma pasta que o usuário já tinha, apagar o
registro no painel não podia apagar o servidor Minecraft dele.

Com o runtime de container o Core passou a **criar e ser dono** de coisas:
diretório da instância, container, backups. Manter a regra antiga para essas
transformou "remover" em vazamento — no servidor de produção sobraram 17 GB de
pastas e um container de instâncias que já não existiam.

A regra nova separa por dono:

- o que o Core criou (pasta gerenciada, container, backups) é removido;
- o que o usuário apontou (pasta adotada) permanece intocado;
- o que é compartilhado (imagens, redes) nunca é tocado — outra instância pode
  depender, e uma imagem é re-baixável mas uma remoção errada não.

Cada etapa é independente: falha em uma não impede as outras, e tudo que falhou
volta no relatório para a interface mostrar em vez de sumir num log.
"""

import asyncio
import contextlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from aether_core.domain.instances import Instance

log = logging.getLogger(__name__)


@dataclass
class RelatorioDeRemocao:
    """O que saiu do disco, para a interface contar ao usuário."""

    container_removido: bool = False
    instalacao_cancelada: bool = False
    pasta_removida: str = ""
    pasta_preservada: str = ""
    """Pasta adotada: o servidor é do usuário, não nosso para apagar."""
    backups_removidos: int = 0
    bytes_liberados: int = 0
    registros_removidos: dict[str, int] = field(default_factory=dict)
    falhas: list[str] = field(default_factory=list)


def _tamanho(caminho: Path) -> int:
    """Quanto ocupa, para reportar o espaço liberado. Melhor errar para menos
    do que falhar a remoção por causa de um arquivo ilegível."""
    total = 0
    with contextlib.suppress(OSError):
        for item in caminho.rglob("*"):
            with contextlib.suppress(OSError):
                if item.is_file() and not item.is_symlink():
                    total += item.stat().st_size
    return total


class InstanceRemover:
    def __init__(
        self,
        instances_dir: Path,
        backups_dir: Path,
        runtime=None,
        docker_supervisor=None,
        installs=None,
    ) -> None:
        self._instances_dir = instances_dir
        self._backups_dir = backups_dir
        self._runtime = runtime
        self._docker_supervisor = docker_supervisor
        self._installs = installs

    def e_gerenciada(self, instance: Instance) -> bool:
        """A pasta foi criada pelo Core (dentro do diretório de instâncias)?

        É o que distingue "servidor que o painel criou" de "pasta que o usuário
        apontou" sem precisar de nova coluna no banco.
        """
        try:
            raiz = Path(instance.root_dir).resolve()
            return raiz.is_relative_to(self._instances_dir.resolve())
        except (OSError, ValueError):
            return False

    async def remove(self, instance: Instance, *, apagar_dados: bool = True) -> RelatorioDeRemocao:
        relatorio = RelatorioDeRemocao()
        log.info("removendo instância %s (%s)", instance.id, instance.name)

        # Primeiro parar quem ainda escreve: um download em andamento recria a
        # pasta logo depois de ela ser apagada.
        if self._installs is not None:
            with contextlib.suppress(Exception):
                relatorio.instalacao_cancelada = await self._installs.cancelar(instance.id)

        await self._remover_container(instance, relatorio)
        if apagar_dados:
            self._remover_pasta(instance, relatorio)
            self._remover_backups(instance, relatorio)
        else:
            relatorio.pasta_preservada = instance.root_dir

        log.info(
            "instância %s removida: container=%s pasta=%r backups=%d liberados=%d falhas=%s",
            instance.id,
            relatorio.container_removido,
            relatorio.pasta_removida,
            relatorio.backups_removidos,
            relatorio.bytes_liberados,
            relatorio.falhas or "nenhuma",
        )
        return relatorio

    # ------------------------------------------------------------------ etapas
    async def _remover_container(self, instance: Instance, rel: RelatorioDeRemocao) -> None:
        """O container é exclusivo da instância — o nome carrega o id dela.

        A imagem fica: é compartilhada com outras instâncias do mesmo jogo e
        re-baixável, então apagá-la custaria um download de gigabytes a quem
        ainda a usa.
        """
        if self._runtime is None:
            return
        try:
            gerenciados = await self._runtime.list_managed()
        except Exception as exc:  # noqa: BLE001 - sem Docker não há container a remover
            log.info("não foi possível listar containers ao remover %s: %s", instance.id, exc)
            return

        for mc in gerenciados:
            if mc.instance_id != instance.id:
                continue
            try:
                await self._runtime.remove(mc.container_id)
                rel.container_removido = True
            except Exception as exc:  # noqa: BLE001
                rel.falhas.append(f"container {mc.container_id[:12]}: {exc}")

        if self._docker_supervisor is not None:
            self._docker_supervisor.forget(instance.id)

    def _remover_pasta(self, instance: Instance, rel: RelatorioDeRemocao) -> None:
        raiz = Path(instance.root_dir)
        if not self.e_gerenciada(instance):
            # Pasta adotada: o servidor existia antes do painel e continua
            # existindo depois dele.
            rel.pasta_preservada = instance.root_dir
            return
        if not raiz.is_dir():
            return
        rel.bytes_liberados += _tamanho(raiz)
        try:
            shutil.rmtree(raiz)
            rel.pasta_removida = str(raiz)
        except OSError as exc:
            rel.falhas.append(f"pasta {raiz}: {exc}")

    def _remover_backups(self, instance: Instance, rel: RelatorioDeRemocao) -> None:
        pasta = self._backups_dir / instance.id
        if not pasta.is_dir():
            return
        rel.backups_removidos = sum(1 for _ in pasta.glob("*.zip"))
        rel.bytes_liberados += _tamanho(pasta)
        try:
            shutil.rmtree(pasta)
        except OSError as exc:
            rel.falhas.append(f"backups {pasta}: {exc}")

    # ------------------------------------------------------------- manutenção
    async def limpar_containers_orfaos(self, ids_vivos: set[str]) -> list[str]:
        """Remove containers de instâncias que já não existem.

        Roda no startup para varrer o que ficou de versões anteriores ou de um
        Core que morreu no meio de uma remoção.
        """
        if self._runtime is None:
            return []
        removidos: list[str] = []
        with contextlib.suppress(Exception):
            for mc in await self._runtime.list_managed():
                if mc.instance_id and mc.instance_id not in ids_vivos:
                    with contextlib.suppress(Exception):
                        await self._runtime.remove(mc.container_id)
                        removidos.append(mc.instance_id)
        if removidos:
            log.info("containers órfãos removidos: %s", removidos)
        return removidos

    async def limpar_pastas_orfas(self, ids_vivos: set[str], raizes_vivas: set[str]) -> list[str]:
        """Remove diretórios gerenciados sem instância correspondente.

        Só mexe no diretório de instâncias do Core: pasta adotada nunca entra
        aqui, porque nunca esteve sob a nossa guarda.
        """
        if not self._instances_dir.is_dir():
            return []
        removidas: list[str] = []
        for pasta in self._instances_dir.iterdir():
            if not pasta.is_dir() or str(pasta.resolve()) in raizes_vivas:
                continue
            try:
                await asyncio.to_thread(shutil.rmtree, pasta)
                removidas.append(str(pasta))
            except OSError as exc:
                log.warning("não foi possível remover a pasta órfã %s: %s", pasta, exc)
        if removidas:
            log.info("pastas órfãs removidas: %s", removidas)
        return removidas
