"""Atualizar o próprio Aether: buscar a `main`, reinstalar e reiniciar.

Atualizar a aplicação de dentro dela mesma tem duas armadilhas que moldaram este
módulo:

- **o processo mata a si mesmo**. Um ``systemctl restart`` chamado de dentro da
  própria unit derruba o Core no meio da resposta HTTP, e o usuário vê um erro
  de rede no lugar de "atualizado com sucesso". Por isso o reinício é agendado
  num processo desacoplado, depois de a resposta já ter saído.
- **alguém edita arquivo direto no servidor**. Acontece justamente na urgência,
  e um ``git pull`` que sobrescreve esse ajuste sem avisar destrói trabalho.
  A atualização recusa e mostra o que está modificado.

O banco é copiado antes de qualquer coisa: migração nova que dê errado precisa
ter volta.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from aether_core.application.events import EventBus
from aether_core.domain.errors import ConflictError, ValidationFailedError

log = logging.getLogger(__name__)

TIMEOUT_COMANDO = 900
"""15 minutos: `uv sync` e o build do painel são lentos em máquina modesta."""


@dataclass
class StatusDaAtualizacao:
    """O que o painel mostra antes de o usuário decidir atualizar."""

    gerenciavel: bool
    """Instalação feita pelo install.sh (um clone git) — só nela dá para atualizar."""
    motivo: str = ""
    branch: str = ""
    commit: str = ""
    commit_curto: str = ""
    data_do_commit: str = ""
    assunto: str = ""
    alteracoes_locais: list[str] = field(default_factory=list)
    commits_atras: int = 0
    atualizando: bool = False


def _git(dir_: Path, *args: str, cru: bool = False) -> str:
    """Roda git e devolve a saída.

    ``cru`` preserva os espaços: o formato do ``status --porcelain`` codifica o
    estado nas duas primeiras colunas, e um ``strip()`` no começo desalinha o
    caminho do arquivo.
    """
    resultado = subprocess.run(
        ["git", "-C", str(dir_), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if resultado.returncode != 0:
        raise ValidationFailedError((resultado.stderr or resultado.stdout).strip())
    return resultado.stdout if cru else resultado.stdout.strip()


class UpdateService:
    def __init__(
        self,
        repo_dir: Path,
        data_dir: Path,
        bus: EventBus,
        service_name: str = "aether-core",
        branch: str = "main",
    ) -> None:
        self._dir = Path(repo_dir)
        self._data_dir = Path(data_dir)
        self._bus = bus
        self._servico = service_name
        self._branch = branch
        self._rodando = False

    # ------------------------------------------------------------------ status
    def status(self, *, buscar_remoto: bool = True) -> StatusDaAtualizacao:
        if not (self._dir / ".git").is_dir():
            return StatusDaAtualizacao(
                gerenciavel=False,
                motivo=(
                    f"{self._dir} não é um clone git, então não há de onde buscar "
                    "atualizações. Instalações feitas com o install.sh já vêm prontas "
                    "para isto."
                ),
            )
        if not shutil.which("git"):
            return StatusDaAtualizacao(gerenciavel=False, motivo="git não está instalado.")

        try:
            branch = _git(self._dir, "rev-parse", "--abbrev-ref", "HEAD")
            commit = _git(self._dir, "rev-parse", "HEAD")
            assunto = _git(self._dir, "log", "-1", "--format=%s")
            data = _git(self._dir, "log", "-1", "--format=%cI")
            sujos = [
                linha[3:].strip()
                for linha in _git(self._dir, "status", "--porcelain", cru=True).splitlines()
                if linha.strip()
            ]
            atras = 0
            if buscar_remoto:
                try:
                    _git(self._dir, "fetch", "--quiet", "origin", self._branch)
                    atras = int(
                        _git(self._dir, "rev-list", "--count", f"HEAD..origin/{self._branch}") or 0
                    )
                except ValidationFailedError as exc:
                    # Sem rede o painel ainda deve abrir; só não sabemos o quanto falta.
                    log.info("não foi possível consultar o remoto: %s", exc)
        except ValidationFailedError as exc:
            return StatusDaAtualizacao(gerenciavel=False, motivo=str(exc))

        return StatusDaAtualizacao(
            gerenciavel=True,
            branch=branch,
            commit=commit,
            commit_curto=commit[:8],
            data_do_commit=data,
            assunto=assunto,
            alteracoes_locais=sujos,
            commits_atras=atras,
            atualizando=self._rodando,
        )

    # ------------------------------------------------------------- atualização
    async def update(self) -> dict:
        status = self.status()
        if not status.gerenciavel:
            raise ValidationFailedError(status.motivo)
        if self._rodando:
            raise ConflictError("já existe uma atualização em andamento")
        if status.alteracoes_locais:
            raise ValidationFailedError(
                "há alterações locais não commitadas em "
                f"{self._dir}: {', '.join(status.alteracoes_locais[:10])}"
                f"{'…' if len(status.alteracoes_locais) > 10 else ''}. "
                "Atualizar sobrescreveria esse trabalho — resolva antes."
            )

        self._rodando = True
        try:
            await self._passo("Copiando o banco de dados", "backup")
            copia = await asyncio.to_thread(self._copiar_banco)
            if copia:
                await self._log(f"banco salvo em {copia}")

            await self._passo(f"Buscando alterações da branch {self._branch}", "pull")
            await self._rodar("git", "fetch", "--quiet", "origin", self._branch)
            # --ff-only: se o histórico divergiu, é melhor parar do que criar um
            # merge automático no servidor de produção.
            await self._rodar("git", "pull", "--ff-only", "origin", self._branch)

            await self._passo("Atualizando dependências Python", "deps")
            await self._rodar("uv", "sync", "--all-packages")

            if (self._dir / "apps" / "dashboard" / "package.json").is_file():
                await self._passo("Compilando o painel", "build")
                await self._rodar("corepack", "pnpm", "install", "--silent")
                await self._rodar("corepack", "pnpm", "--dir", "apps/dashboard", "build")

            novo = self.status(buscar_remoto=False)
            await self._passo("Reiniciando o serviço", "restart")
            # As migrações rodam sozinhas no start do Core (run_migrations no
            # create_app), então não há passo separado para elas.
            self._agendar_reinicio()
            await self._bus.publish(
                "update.progress",
                {"etapa": "done", "status": "done", "commit": novo.commit_curto},
            )
            return {
                "commit": novo.commit,
                "commit_curto": novo.commit_curto,
                "assunto": novo.assunto,
                "banco_salvo_em": str(copia) if copia else "",
                "reiniciando": True,
            }
        except Exception as exc:
            await self._bus.publish(
                "update.progress", {"etapa": "erro", "status": "error", "erro": str(exc)}
            )
            raise
        finally:
            self._rodando = False

    # ---------------------------------------------------------------- internos
    def _copiar_banco(self) -> Path | None:
        banco = self._data_dir / "aether.db"
        if not banco.is_file():
            return None
        destino = self._data_dir / "updates" / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        destino.mkdir(parents=True, exist_ok=True)
        alvo = destino / "aether.db"
        shutil.copy2(banco, alvo)
        return alvo

    @staticmethod
    def _resolver(programa: str) -> str:
        """Caminho completo do executável, procurando além do PATH do systemd.

        A unit roda com um PATH enxuto que não inclui ~/.local/bin, onde o uv se
        instala. Sem isto o erro chega ao usuário como um FileNotFoundError sem
        contexto, e o culpado é invisível.
        """
        caminho = shutil.which(programa)
        if caminho:
            return caminho
        extra = f"{os.environ.get('PATH', '')}:{Path.home() / '.local/bin'}:/usr/local/bin"
        caminho = shutil.which(programa, path=extra)
        if caminho:
            return caminho
        raise ValidationFailedError(
            f"'{programa}' não foi encontrado no servidor. "
            "Reinstale com o install.sh ou garanta que ele esteja no PATH do serviço."
        )

    async def _rodar(self, *comando: str) -> None:
        comando = (self._resolver(comando[0]), *comando[1:])
        proc = await asyncio.create_subprocess_exec(
            *comando,
            cwd=str(self._dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        linhas: list[str] = []
        while True:
            bruto = await proc.stdout.readline()
            if not bruto:
                break
            linha = bruto.decode("utf-8", "replace").rstrip()
            if linha:
                linhas.append(linha)
                await self._log(linha)
        try:
            code = await asyncio.wait_for(proc.wait(), TIMEOUT_COMANDO)
        except TimeoutError as exc:
            proc.kill()
            raise ValidationFailedError(f"{comando[0]} demorou demais e foi interrompido") from exc
        if code != 0:
            raise ValidationFailedError(
                f"'{' '.join(comando)}' falhou (código {code}): {linhas[-1] if linhas else ''}"
            )

    def _agendar_reinicio(self) -> None:
        """Reinicia o serviço sem matar a resposta que ainda está sendo enviada.

        `start_new_session` tira o processo do grupo do Core: quando o systemd
        derrubar a unit, este comando sobrevive e conclui o restart.
        """
        subprocess.Popen(  # noqa: S603 - comando fixo, sem entrada do usuário
            ["sh", "-c", f"sleep 2; systemctl restart {self._servico}"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def _passo(self, descricao: str, etapa: str) -> None:
        log.info("atualização: %s", descricao)
        await self._bus.publish(
            "update.progress", {"etapa": etapa, "status": "running", "descricao": descricao}
        )

    async def _log(self, linha: str) -> None:
        await self._bus.publish("update.progress", {"etapa": "log", "linha": linha})
