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
import shutil
from datetime import UTC, datetime
from pathlib import Path

from aether_sdk import LaunchContext, SupportsInstall, SupportsInstallSize, VersionInfo

from aether_core.application.events import EventBus
from aether_core.application.ports import ContainerRuntime, ProviderRegistry
from aether_core.domain.backups import BackupKind
from aether_core.domain.errors import ConflictError, EmptyBackupError, ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState

log = logging.getLogger(__name__)

TTL_VERSOES_SEGUNDOS = 10 * 60
"""Dez minutos: curto o bastante para um lançamento aparecer quase na hora,
longo o bastante para uma sessão inteira de configuração não repetir a consulta."""


def _idade(quando: datetime) -> float:
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=UTC)
    return (datetime.now(UTC) - quando).total_seconds()


def _gb(bytes_: int) -> str:
    return f"{bytes_ / 1024**3:.1f} GB"


class InstallService:
    def __init__(
        self,
        runtime: ContainerRuntime,
        providers: ProviderRegistry,
        supervisor,
        bus: EventBus,
        persistir=None,
        ler_versoes=None,
        guardar_versoes=None,
    ) -> None:
        self._runtime = runtime
        self._providers = providers
        self._supervisor = supervisor
        self._bus = bus
        # Guardar o resultado precisa de uma sessão própria: a tarefa de fundo
        # sobrevive à request que a disparou.
        self._persistir = persistir
        self._ler_versoes = ler_versoes
        self._guardar_versoes = guardar_versoes
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

    async def versions(self, provider_id: str, *, atualizar: bool = False) -> list[VersionInfo]:
        """Versões oferecidas pela origem do jogo, com cache no banco.

        Perguntar à origem custa um container efêmero e segundos de espera; a
        resposta muda poucas vezes por semana. Dentro do TTL a tela abre na
        hora, e fora dele um erro de rede cai para o que já se sabia — origem
        fora do ar não pode esvaziar a lista de quem já tinha uma.
        """
        provider = self._provider(provider_id)
        spec = provider.versions_spec()
        if spec is None:
            return provider.parse_versions("")

        anterior = await self._cache_versoes(provider_id)
        if anterior is not None:
            versoes, quando = anterior
            if not atualizar and _idade(quando) < TTL_VERSOES_SEGUNDOS:
                return versoes
        try:
            _, saida = await self._runtime.run_once(spec, Path("/tmp"))
            versoes = provider.parse_versions(saida)
        except Exception as exc:  # noqa: BLE001 - origem fora do ar não é erro nosso
            log.warning("não foi possível listar versões de %s: %s", provider_id, exc)
            return anterior[0] if anterior else []

        if versoes and self._guardar_versoes is not None:
            with contextlib.suppress(Exception):
                await self._guardar_versoes(provider_id, [v.model_dump() for v in versoes])
        return versoes

    async def _cache_versoes(self, provider_id: str) -> tuple[list[VersionInfo], datetime] | None:
        if self._ler_versoes is None:
            return None
        try:
            guardado = await self._ler_versoes(provider_id)
        except Exception:  # noqa: BLE001 - cache é atalho, não fonte da verdade
            log.exception("falha ao ler o cache de versões de %s", provider_id)
            return None
        if not guardado:
            return None
        bruto, quando = guardado
        return [VersionInfo.model_validate(v) for v in bruto], quando

    def installed_version(self, instance: Instance) -> str:
        provider = self._provider(instance.provider_id)
        return provider.installed_version(Path(instance.root_dir))

    def espaco(self, instance: Instance, version: str = "") -> tuple[int, int]:
        """(livre, necessário) em bytes. Necessário ``0`` quando ninguém sabe."""
        provider = self._providers.get(instance.provider_id)
        preciso = 0
        if isinstance(provider, SupportsInstallSize):
            preciso = int(provider.install_disk_bytes(version) or 0)
        alvo = Path(instance.root_dir)
        # A pasta da instância pode ainda não existir; o que importa é o
        # sistema de arquivos onde ela vai morar.
        while not alvo.exists() and alvo != alvo.parent:
            alvo = alvo.parent
        try:
            livre = shutil.disk_usage(alvo).free
        except OSError:
            livre = 0
        return livre, preciso

    def checar_disco(self, instance: Instance, version: str = "") -> None:
        """Recusa a instalação quando o disco não comporta.

        Esta checagem existe porque a falha sem ela é cruel: o download vai até
        99%, o instalador aborta no meio da gravação, e o que sobra é uma pasta
        de 17 GB com um servidor que não inicia e nenhuma pista do motivo.
        """
        livre, preciso = self.espaco(instance, version)
        if preciso and livre < preciso:
            raise ValidationFailedError(
                f"espaço em disco insuficiente: a instalação precisa de "
                f"{_gb(preciso)} livres e há {_gb(livre)}. O instalador baixa os "
                f"arquivos numa pasta de trabalho antes de gravar os definitivos, "
                f"então chega a ocupar o dobro do tamanho final do jogo."
            )

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
        self.checar_disco(instance, version)
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
            except Exception as exc:  # noqa: BLE001 - vira estado, não desaparece
                log.warning("instalação de %s falhou: %s", instance.id, exc)
                # Guardar o motivo é o que separa "não iniciou porque a
                # instalação falhou por falta de disco" de um erro opaco na
                # hora de dar play, dias depois, sem nada no console.
                if self._persistir is not None:
                    with contextlib.suppress(Exception):
                        await self._persistir(
                            instance.id,
                            {"install": {"error": str(exc), "version": version}},
                        )
            finally:
                self._em_andamento.discard(instance.id)

        self._tarefas[instance.id] = asyncio.create_task(tarefa())

    async def cancelar(self, instance_id: str) -> bool:
        """Interrompe uma instalação em andamento.

        Necessário na remoção: sem isto o download continuaria gravando numa
        pasta que está sendo apagada — o SteamCMD recria o diretório e a
        remoção "bem-sucedida" deixa lixo para trás.
        """
        tarefa = self._tarefas.pop(instance_id, None)
        self._em_andamento.discard(instance_id)
        if tarefa is None or tarefa.done():
            return False
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa
        return True

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
                    await self._console(instance, f"[aether] backup criado: {backup.file_name}")
                except EmptyBackupError:
                    # Instalação anterior incompleta deixa o manifesto do jogo
                    # sem nenhum dado do usuário. Exigir backup aqui criaria um
                    # impasse: não instala porque o backup falha, e o backup
                    # falha porque ainda não há o que salvar.
                    await self._console(
                        instance, "[aether] nada a salvar ainda; seguindo sem backup."
                    )
                except Exception as exc:  # noqa: BLE001
                    await self._console(
                        instance, f"[aether] backup falhou, atualização cancelada: {exc}", "ERROR"
                    )
                    await self._publicar(instance, "error", version, erro=str(exc))
                    raise ValidationFailedError(
                        f"a atualização foi cancelada porque o backup falhou: {exc}"
                    ) from exc

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
