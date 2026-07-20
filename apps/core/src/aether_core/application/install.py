"""Instalar e atualizar o servidor de uma instância.

Atualizar servidor de jogo é das operações mais arriscadas do painel: mexe nos
arquivos que o mundo do jogador depende, demora, e quando dá errado o estrago
já aconteceu. Por isso o serviço impõe uma ordem que não é negociável:

    parado → backup → instalação → preparo da config

O backup vem antes de qualquer arquivo ser tocado, e falha de backup aborta a
atualização. Melhor não atualizar do que atualizar sem rede de segurança.
"""

import asyncio
import contextlib
import logging
from pathlib import Path

from aether_sdk import LaunchContext, SupportsInstall, VersionInfo

from aether_core.application.events import EventBus
from aether_core.application.ports import ContainerRuntime, ProviderRegistry
from aether_core.domain.backups import BackupKind
from aether_core.domain.errors import ConflictError, ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState

log = logging.getLogger(__name__)


class InstallService:
    def __init__(
        self,
        runtime: ContainerRuntime,
        providers: ProviderRegistry,
        supervisor,
        bus: EventBus,
        persistir=None,
    ) -> None:
        self._runtime = runtime
        self._providers = providers
        self._supervisor = supervisor
        self._bus = bus
        # Guardar o resultado precisa de uma sessão própria: a tarefa de fundo
        # sobrevive à request que a disparou.
        self._persistir = persistir
        self._em_andamento: set[str] = set()
        self._tarefas: dict[str, asyncio.Task] = {}

    # ---------------------------------------------------------------- consultas
    def _provider(self, provider_id: str) -> SupportsInstall:
        provider = self._providers.get(provider_id)
        if not isinstance(provider, SupportsInstall):
            raise ValidationFailedError(f"provider {provider_id!r} does not manage server versions")
        return provider

    def rodando(self, instance_id: str) -> bool:
        return instance_id in self._em_andamento

    async def versions(self, provider_id: str) -> list[VersionInfo]:
        """Versões oferecidas pela origem do jogo.

        Erro de rede devolve lista vazia em vez de quebrar: a tela de criação
        precisa abrir mesmo com a Steam fora do ar.
        """
        provider = self._provider(provider_id)
        spec = provider.versions_spec()
        if spec is None:
            return provider.parse_versions("")
        try:
            _, saida = await self._runtime.run_once(spec, Path("/tmp"))
            return provider.parse_versions(saida)
        except Exception as exc:  # noqa: BLE001 - origem fora do ar não é erro nosso
            log.warning("não foi possível listar versões de %s: %s", provider_id, exc)
            return []

    def installed_version(self, instance: Instance) -> str:
        provider = self._provider(instance.provider_id)
        return provider.installed_version(Path(instance.root_dir))

    # --------------------------------------------------------------- instalação
    async def start(
        self,
        instance: Instance,
        version: str,
        *,
        backup_service=None,
        skip_backup: bool = False,
    ) -> None:
        """Dispara a instalação em segundo plano e devolve na hora.

        Baixar 17 GB não cabe numa request HTTP: ela morreria de timeout e o
        usuário não veria progresso. As validações que o usuário precisa saber
        na hora (servidor no ar, instalação já rodando) acontecem antes.
        """
        provider = self._provider(instance.provider_id)
        if self._supervisor.state(instance.id) is not InstanceState.STOPPED:
            raise ConflictError("pare o servidor antes de instalar ou atualizar")
        if instance.id in self._em_andamento:
            raise ConflictError("já existe uma instalação em andamento")
        provider.install_spec(
            LaunchContext(root_dir=Path(instance.root_dir), provider_data=instance.provider_data),
            version,
        )

        self._em_andamento.add(instance.id)

        async def tarefa() -> None:
            try:
                resultado = await self.install(
                    instance,
                    version,
                    backup_service=backup_service,
                    skip_backup=skip_backup,
                    _ja_reservado=True,
                )
                if self._persistir is not None:
                    await self._persistir(instance.id, resultado)
            except Exception as exc:  # noqa: BLE001 - já reportado no console/evento
                log.warning("instalação de %s falhou: %s", instance.id, exc)
            finally:
                self._em_andamento.discard(instance.id)

        self._tarefas[instance.id] = asyncio.create_task(tarefa())

    async def shutdown(self) -> None:
        for tarefa in self._tarefas.values():
            tarefa.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarefa

    async def install(
        self,
        instance: Instance,
        version: str,
        *,
        backup_service=None,
        skip_backup: bool = False,
        _ja_reservado: bool = False,
    ) -> dict:
        """Instala ou atualiza o servidor. Devolve o que mudou, para a interface
        contar ao usuário (config criada, propriedades novas da versão)."""
        provider = self._provider(instance.provider_id)

        if not _ja_reservado:
            if self._supervisor.state(instance.id) is not InstanceState.STOPPED:
                raise ConflictError("pare o servidor antes de instalar ou atualizar")
            if instance.id in self._em_andamento:
                raise ConflictError("já existe uma instalação em andamento")
            self._em_andamento.add(instance.id)
        try:
            await self._publicar(instance, "started", version)

            # O backup precisa existir ANTES de qualquer arquivo ser tocado.
            # Só faz sentido quando já há o que salvar: numa instalação nova a
            # instância está vazia.
            primeira = not provider.installed_version(Path(instance.root_dir))
            if backup_service is not None and not skip_backup and not primeira:
                await self._console(instance, "[aether] criando backup antes de atualizar…")
                try:
                    backup = await backup_service.create(
                        instance, kind=BackupKind.MANUAL, note=f"antes de atualizar ({version})"
                    )
                except Exception as exc:  # noqa: BLE001
                    await self._console(
                        instance, f"[aether] backup falhou, atualização cancelada: {exc}", "ERROR"
                    )
                    await self._publicar(instance, "error", version, erro=str(exc))
                    raise ValidationFailedError(
                        f"a atualização foi cancelada porque o backup falhou: {exc}"
                    ) from exc
                await self._console(instance, f"[aether] backup criado: {backup.file_name}")

            await self._console(instance, f"[aether] instalando a versão {version}…")
            spec = provider.install_spec(
                LaunchContext(
                    root_dir=Path(instance.root_dir), provider_data=instance.provider_data
                ),
                version,
            )

            async def repassar(linha: str) -> None:
                await self._console(instance, linha)

            code, _ = await self._runtime.run_once(spec, Path(instance.root_dir), on_line=repassar)
            if code != 0:
                await self._publicar(instance, "error", version, erro=f"exit {code}")
                raise ValidationFailedError(f"a instalação falhou (código {code})")

            # Só agora os arquivos do jogo existem — é aqui que o provider
            # consegue preparar a configuração a partir do que veio na versão.
            mudancas = provider.after_install(Path(instance.root_dir), instance.provider_data)
            resumo = dict(mudancas.get("install") or {})
            if resumo.get("config_seeded"):
                await self._console(instance, "[aether] configuração criada a partir da versão.")
            novas = resumo.get("new_properties") or []
            if novas:
                await self._console(
                    instance,
                    f"[aether] a versão trouxe {len(novas)} configuração(ões) nova(s): "
                    + ", ".join(novas[:8])
                    + ("…" if len(novas) > 8 else ""),
                )
            await self._console(instance, "[aether] instalação concluída.")
            await self._publicar(instance, "done", version)
            return {"version": version, **mudancas}
        finally:
            if not _ja_reservado:
                self._em_andamento.discard(instance.id)

    # ----------------------------------------------------------------- interno
    async def _console(self, instance: Instance, linha: str, level: str = "INFO") -> None:
        await self._bus.publish(
            f"instance.{instance.id}.console", {"line": linha, "level": level, "ready": False}
        )

    async def _publicar(self, instance: Instance, status: str, version: str, **extra) -> None:
        await self._bus.publish(
            f"instance.{instance.id}.job",
            {"kind": "install", "status": status, "version": version, **extra},
        )
