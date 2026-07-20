"""Gerenciamento de jogadores.

A regra que dá razão a este módulo: **com o servidor no ar, quem edita as
listas é o servidor.** Ele as mantém em memória e reescreve os arquivos quando
quer, então gravar por baixo dele faz a alteração desaparecer sem erro nenhum —
o usuário adiciona um amigo à whitelist, vê a tela confirmar, e o amigo não
entra.

Por isso a decisão é tomada aqui e não no provider: rodando manda comando de
console; parado escreve o arquivo.
"""

from pathlib import Path

from aether_sdk import LIVE_ONLY, PlayerAction, PlayerList, SupportsPlayers

from aether_core.application.events import EventBus
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState


class PlayerService:
    def __init__(self, providers, power, bus: EventBus) -> None:
        self._providers = providers
        self._power = power
        self._bus = bus

    def _provider(self, instance: Instance) -> SupportsPlayers:
        p = self._providers.get(instance.provider_id)
        if not isinstance(p, SupportsPlayers):
            raise ValidationFailedError(
                f"o provider {instance.provider_id!r} não gerencia jogadores"
            )
        return p

    def lists(self, instance: Instance) -> list[PlayerList]:
        return self._provider(instance).player_lists(Path(instance.root_dir))

    async def apply(
        self, instance: Instance, action: PlayerAction, name: str, reason: str = ""
    ) -> str:
        """Aplica a ação pelo caminho correto para o estado atual.

        Devolve qual caminho foi usado, porque a diferença importa para quem
        está olhando: por console o efeito é imediato, por arquivo só vale a
        partir do próximo boot.
        """
        provider = self._provider(instance)
        name = name.strip()
        if not name:
            raise ValidationFailedError("informe o nome do jogador")

        rodando = self._power.state(instance) is InstanceState.RUNNING

        if not rodando and action in LIVE_ONLY:
            raise ValidationFailedError("esta ação só funciona com o servidor rodando")

        if rodando:
            comando = provider.player_command(action, name, reason)
            if comando is None:
                raise ValidationFailedError(f"ação não suportada: {action}")
            await self._power.send_command(instance, comando)
            via = "console"
        else:
            provider.apply_player_action(Path(instance.root_dir), action, name, reason)
            via = "arquivo"

        await self._bus.publish(
            "players.changed",
            {"instance_id": instance.id, "action": str(action), "player": name, "via": via},
        )
        return via
