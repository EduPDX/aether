"""Casos de uso de backup: criar, listar, restaurar, apagar e podar.

O Core sabe compactar, agendar e reter; o provider diz o que entra e como
deixar o disco consistente (ver ``aether_sdk.backup``).
"""

import asyncio
import shutil
import uuid
import zipfile
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Protocol

from aether_sdk import BackupSpec, QuiescePlan, SupportsBackup

from aether_core.application.events import EventBus
from aether_core.application.ports import ProviderRegistry
from aether_core.domain.backups import (
    Backup,
    BackupKind,
    BackupPolicy,
    backup_file_name,
    select_for_pruning,
)
from aether_core.domain.errors import (
    ConflictError,
    EmptyBackupError,
    NotFoundError,
    ValidationFailedError,
)
from aether_core.domain.instances import Instance, InstanceState


class BackupRepository(Protocol):
    async def add(self, backup: Backup) -> None: ...

    async def list_for(self, instance_id: str) -> list[Backup]: ...

    async def get(self, backup_id: str) -> Backup | None: ...

    async def delete(self, backup_id: str) -> bool: ...

    async def get_policy(self, instance_id: str) -> BackupPolicy: ...

    async def set_policy(self, instance_id: str, policy: BackupPolicy) -> None: ...

    async def last_run(self, instance_id: str) -> datetime | None: ...

    async def mark_run(self, instance_id: str, when: datetime) -> None: ...


class SupervisorLike(Protocol):
    def state(self, instance_id: str) -> InstanceState: ...

    async def send_command(self, instance_id: str, command: str) -> None: ...


def collect_files(root: Path, spec: BackupSpec) -> list[Path]:
    """Arquivos que entram no backup, resolvendo include/exclude.

    Exclusão vence inclusão, o que permite pegar uma pasta inteira e descartar
    o que é grande e reproduzível.

    O sufixo ``/**`` é expandido à mão, sem passar por ``Path.glob``: até o
    Python 3.12 esse padrão devolve apenas diretórios, e só a partir do 3.13
    passou a incluir arquivos. Depender disso faria o backup sair vazio no
    interpretador de produção enquanto passa nos testes de quem desenvolve num
    Python mais novo — falha silenciosa exatamente onde ela custa mais caro.
    """

    def excluido(rel: str) -> bool:
        return any(fnmatch(rel, padrao) for padrao in spec.exclude)

    encontrados: dict[str, Path] = {}
    for padrao in spec.include:
        if padrao.endswith("/**"):
            base = root / padrao[:-3]
            candidatos = base.rglob("*") if base.is_dir() else iter(())
        else:
            candidatos = root.glob(padrao)
        for caminho in candidatos:
            if not caminho.is_file():
                continue
            rel = caminho.relative_to(root).as_posix()
            if not excluido(rel):
                encontrados[rel] = caminho
    return [encontrados[k] for k in sorted(encontrados)]


class BackupService:
    def __init__(
        self,
        repo: BackupRepository,
        providers: ProviderRegistry,
        supervisor: SupervisorLike,
        bus: EventBus,
        backups_root: Path,
    ) -> None:
        self._repo = repo
        self._providers = providers
        self._supervisor = supervisor
        self._bus = bus
        self._root = backups_root

    # ------------------------------------------------------------------ specs
    def _spec(self, instance: Instance) -> BackupSpec:
        provider = self._providers.get(instance.provider_id)
        if not isinstance(provider, SupportsBackup):
            raise ValidationFailedError(
                f"o provider {instance.provider_id!r} não sabe fazer backup"
            )
        return provider.backup_spec(Path(instance.root_dir))

    def _quiesce(self, instance: Instance) -> QuiescePlan:
        provider = self._providers.get(instance.provider_id)
        plano = getattr(provider, "quiesce_plan", None)
        return plano() if callable(plano) else QuiescePlan()

    def describe(self, instance: Instance) -> dict:
        spec = self._spec(instance)
        return {
            "include": list(spec.include),
            "exclude": list(spec.exclude),
            "summary": spec.summary,
        }

    def folder_for(self, instance_id: str) -> Path:
        return self._root / instance_id

    # ----------------------------------------------------------------- create
    async def create(
        self,
        instance: Instance,
        kind: BackupKind = BackupKind.MANUAL,
        note: str = "",
    ) -> Backup:
        spec = self._spec(instance)
        root = Path(instance.root_dir)
        if not root.is_dir():
            raise NotFoundError(f"raiz da instância não encontrada: {instance.root_dir}")

        destino = self.folder_for(instance.id)
        destino.mkdir(parents=True, exist_ok=True)
        # A identidade é gerada antes do arquivo para dar nome único ao zip.
        backup_id = uuid.uuid4().hex
        nome = backup_file_name(instance.name, datetime.now(UTC), kind, backup_id)
        alvo = destino / nome
        if alvo.exists():
            raise ConflictError(f"já existe um backup com este nome: {nome}")

        rodando = self._supervisor.state(instance.id) is InstanceState.RUNNING
        plano = self._quiesce(instance)

        # Com o servidor no ar, pausa a gravação antes de ler. Sem isso o mundo
        # é escrito durante a cópia e o backup sai com região corrompida.
        pausado = False
        if rodando and plano.before:
            try:
                for comando in plano.before:
                    await self._supervisor.send_command(instance.id, comando)
                pausado = True
                await asyncio.sleep(plano.settle_seconds)
            except Exception:
                pausado = False

        try:
            arquivos = await asyncio.to_thread(collect_files, root, spec)
            if not arquivos:
                raise EmptyBackupError(
                    "nada para salvar: nenhum arquivo casou com o que o provider define como backup"
                )
            tamanho = await asyncio.to_thread(self._write_zip, alvo, root, arquivos)
        except Exception:
            alvo.unlink(missing_ok=True)  # não deixa zip pela metade
            raise
        finally:
            if pausado:
                for comando in plano.after:
                    try:
                        await self._supervisor.send_command(instance.id, comando)
                    except Exception:
                        # Falhar aqui deixaria o mundo sem salvar; registra e segue.
                        await self._bus.publish(
                            "backup.resume_failed",
                            {"instance_id": instance.id, "command": comando},
                        )

        backup = Backup(
            id=backup_id,
            instance_id=instance.id,
            file_name=nome,
            size_bytes=tamanho,
            kind=kind,
            note=note,
        )
        await self._repo.add(backup)
        await self._bus.publish(
            "backup.created",
            {"instance_id": instance.id, "file": nome, "size": tamanho, "kind": kind.value},
        )
        await self.prune(instance)
        return backup

    @staticmethod
    def _write_zip(alvo: Path, root: Path, arquivos: list[Path]) -> int:
        with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for caminho in arquivos:
                zf.write(caminho, caminho.relative_to(root).as_posix())
        return alvo.stat().st_size

    # ------------------------------------------------------------------ query
    async def list_for(self, instance: Instance) -> list[Backup]:
        return await self._repo.list_for(instance.id)

    async def resolve_file(self, instance: Instance, backup_id: str) -> Path:
        backup = await self._get_owned(instance, backup_id)
        caminho = self.folder_for(instance.id) / backup.file_name
        if not caminho.is_file():
            raise NotFoundError("o arquivo do backup não está mais no disco")
        return caminho

    async def _get_owned(self, instance: Instance, backup_id: str) -> Backup:
        backup = await self._repo.get(backup_id)
        # Confere o dono: sem isso um id válido de outra instância daria acesso
        # ao arquivo dela.
        if backup is None or backup.instance_id != instance.id:
            raise NotFoundError(f"backup não encontrado: {backup_id}")
        return backup

    # ----------------------------------------------------------------- delete
    async def delete(self, instance: Instance, backup_id: str) -> None:
        backup = await self._get_owned(instance, backup_id)
        caminho = self.folder_for(instance.id) / backup.file_name
        await asyncio.to_thread(caminho.unlink, True)
        await self._repo.delete(backup_id)
        await self._bus.publish(
            "backup.deleted", {"instance_id": instance.id, "file": backup.file_name}
        )

    async def prune(self, instance: Instance) -> list[str]:
        politica = await self._repo.get_policy(instance.id)
        existentes = await self._repo.list_for(instance.id)
        apagados: list[str] = []
        for backup in select_for_pruning(existentes, politica):
            caminho = self.folder_for(instance.id) / backup.file_name
            await asyncio.to_thread(caminho.unlink, True)
            await self._repo.delete(backup.id)
            apagados.append(backup.file_name)
        return apagados

    # ---------------------------------------------------------------- restore
    async def restore(self, instance: Instance, backup_id: str) -> dict:
        """Extrai o backup sobre a raiz da instância.

        Recusa com o servidor no ar: sobrescrever o mundo enquanto o processo
        o mantém aberto em memória o corrompe e ainda perde o que restaurou
        assim que o servidor salvar por cima.
        """
        if self._supervisor.state(instance.id) is not InstanceState.STOPPED:
            raise ValidationFailedError(
                "pare o servidor antes de restaurar: restaurar com ele no ar corrompe o mundo"
            )
        caminho = await self.resolve_file(instance, backup_id)
        root = Path(instance.root_dir)

        # Antes de sobrescrever, guarda o estado atual: se o backup for o
        # errado, o usuário ainda tem para onde voltar.
        seguranca = await self.create(instance, BackupKind.MANUAL, note="antes de restaurar")

        restaurados = await asyncio.to_thread(self._extract, caminho, root)
        await self._bus.publish(
            "backup.restored",
            {"instance_id": instance.id, "file": caminho.name, "files": restaurados},
        )
        return {"restored_files": restaurados, "safety_backup_id": seguranca.id}

    @staticmethod
    def _extract(zip_path: Path, root: Path) -> int:
        root_resolvido = root.resolve()
        contados = 0
        with zipfile.ZipFile(zip_path) as zf:
            for membro in zf.infolist():
                if membro.is_dir():
                    continue
                # Zip Slip: um zip adulterado com "../" escaparia da instância
                # e escreveria em qualquer lugar do disco.
                destino = (root_resolvido / membro.filename).resolve()
                if not destino.is_relative_to(root_resolvido):
                    raise ValidationFailedError(f"caminho inválido no backup: {membro.filename!r}")
                destino.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(membro) as origem, open(destino, "wb") as saida:
                    shutil.copyfileobj(origem, saida)
                contados += 1
        return contados

    # --------------------------------------------------------------- schedule
    async def get_policy(self, instance_id: str) -> BackupPolicy:
        return await self._repo.get_policy(instance_id)

    async def set_policy(self, instance_id: str, policy: BackupPolicy) -> None:
        await self._repo.set_policy(instance_id, policy)

    async def mark_run(self, instance_id: str, when: datetime) -> None:
        await self._repo.mark_run(instance_id, when)

    async def due(self, instance_id: str, now: datetime) -> bool:
        """Se o agendamento desta instância já venceu."""
        politica = await self._repo.get_policy(instance_id)
        intervalo = politica.interval_seconds()
        if intervalo is None:
            return False
        ultima = await self._repo.last_run(instance_id)
        if ultima is None:
            return True
        return (now - ultima).total_seconds() >= intervalo
