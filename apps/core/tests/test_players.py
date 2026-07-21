"""Gerenciamento de jogadores: listas, UUID e a escolha console vs arquivo."""

import asyncio
import json

import pytest
from aether_core.application.players import PlayerService
from aether_core.domain.errors import ValidationFailedError
from aether_core.domain.instances import Instance, InstanceState
from aether_provider_minecraft.provider import MinecraftProvider
from aether_provider_minecraft.server.players import offline_uuid, player_live_plan
from aether_sdk import PlayerAction, PlayerListKind


def montar(tmp_path, *, online_mode="false", white_list="true"):
    root = tmp_path / "srv"
    root.mkdir(parents=True)
    (root / "server.properties").write_text(
        f"level-name=world\nonline-mode={online_mode}\nwhite-list={white_list}\n"
    )
    (root / "whitelist.json").write_text(json.dumps([{"uuid": offline_uuid("edu"), "name": "edu"}]))
    (root / "ops.json").write_text(
        json.dumps(
            [
                {
                    "uuid": offline_uuid("EduPDX"),
                    "name": "EduPDX",
                    "level": 4,
                    "bypassesPlayerLimit": False,
                }
            ]
        )
    )
    (root / "banned-players.json").write_text(
        json.dumps(
            [
                {
                    "uuid": offline_uuid("Sovnr"),
                    "name": "Sovnr",
                    "created": "2025-05-31 17:49:55 -0300",
                    "source": "Server",
                    "expires": "forever",
                    "reason": "grief",
                }
            ]
        )
    )
    return root


def ler(root, arquivo):
    return json.loads((root / arquivo).read_text())


# --------------------------------------------------------------------- UUID --


def test_offline_uuid_bate_com_o_servidor_real():
    """Conferido contra UUIDs de um servidor de produção em `online-mode=false`.

    Se este teste quebrar, jogador adicionado com o servidor parado vira uma
    entrada que o Minecraft nunca reconhece — e o sintoma é "adicionei e ele
    não entra", sem erro nenhum.
    """
    assert offline_uuid("edu") == "6b8e051e-b71e-34fa-bf61-8eea69fe238c"
    assert offline_uuid("EduPDX") == "fd77046f-cfdc-3499-a8e0-7ea2a5442cd3"
    assert offline_uuid("Biffz0") == "fa0f5c16-bf1a-3f9b-b46e-ef7fd272bde6"
    assert offline_uuid("Sovnr") == "95d4c4c3-deba-3f37-a55e-3a921d39a5f3"


def test_offline_uuid_diferencia_maiusculas():
    """O Minecraft trata os nomes como distintos ao gerar o UUID."""
    assert offline_uuid("edu") != offline_uuid("EDU")


# -------------------------------------------------------------------- leitura --


def test_le_as_tres_listas(tmp_path):
    listas = {le.kind: le for le in MinecraftProvider().player_lists(montar(tmp_path))}

    assert [e.name for e in listas[PlayerListKind.ALLOW].entries] == ["edu"]
    assert [e.name for e in listas[PlayerListKind.ADMIN].entries] == ["EduPDX"]
    assert "nível 4" in listas[PlayerListKind.ADMIN].entries[0].detail
    assert "grief" in listas[PlayerListKind.BANNED].entries[0].detail


def test_avisa_quando_a_whitelist_esta_desligada(tmp_path):
    """`white-list=false` faz o servidor ignorar a lista inteira.

    Sem este sinal o usuário cadastra gente e não entende por que estranhos
    continuam entrando.
    """
    ligada = montar(tmp_path / "a", white_list="true")
    desligada = montar(tmp_path / "b", white_list="false")
    p = MinecraftProvider()

    assert p.player_lists(ligada)[0].enforced is True
    assert p.player_lists(desligada)[0].enforced is False


def test_arquivo_corrompido_nao_derruba_a_tela(tmp_path):
    root = montar(tmp_path)
    (root / "whitelist.json").write_text("{ isto nao e json")
    listas = MinecraftProvider().player_lists(root)
    assert listas[0].entries == ()


# ------------------------------------------------------- escrita com o servidor parado --


def test_adicionar_grava_com_o_uuid_certo(tmp_path):
    root = montar(tmp_path)
    MinecraftProvider().apply_player_action(root, PlayerAction.ALLOW_ADD, "Fulano")

    entradas = {e["name"]: e["uuid"] for e in ler(root, "whitelist.json")}
    assert entradas["Fulano"] == offline_uuid("Fulano")


def test_adicionar_duas_vezes_nao_duplica(tmp_path):
    root = montar(tmp_path)
    p = MinecraftProvider()
    p.apply_player_action(root, PlayerAction.ALLOW_ADD, "Fulano")
    p.apply_player_action(root, PlayerAction.ALLOW_ADD, "fulano")  # caixa diferente

    nomes = [e["name"] for e in ler(root, "whitelist.json")]
    assert nomes.count("Fulano") == 1


def test_banir_tira_da_whitelist(tmp_path):
    """Ficar banido e liberado ao mesmo tempo é contraditório — o próprio
    servidor remove da whitelist ao banir."""
    root = montar(tmp_path)
    MinecraftProvider().apply_player_action(root, PlayerAction.BAN, "edu", "trapaça")

    assert [e["name"] for e in ler(root, "whitelist.json")] == []
    banido = [e for e in ler(root, "banned-players.json") if e["name"] == "edu"][0]
    assert banido["reason"] == "trapaça"


def test_remover_e_desbanir(tmp_path):
    root = montar(tmp_path)
    p = MinecraftProvider()
    p.apply_player_action(root, PlayerAction.ALLOW_REMOVE, "edu")
    p.apply_player_action(root, PlayerAction.UNBAN, "Sovnr")

    assert ler(root, "whitelist.json") == []
    assert ler(root, "banned-players.json") == []


def test_online_mode_com_jogador_desconhecido_falha_com_explicacao(tmp_path):
    """Em modo online o UUID vem da Mojang; inventar geraria entrada morta."""
    root = montar(tmp_path, online_mode="true")
    with pytest.raises(ValueError, match="Mojang"):
        MinecraftProvider().apply_player_action(root, PlayerAction.ALLOW_ADD, "Desconhecido")


def test_online_mode_usa_o_usercache_quando_o_jogador_ja_entrou(tmp_path):
    root = montar(tmp_path, online_mode="true")
    real = "11111111-2222-4333-8444-555555555555"  # UUID de verdade, versão 4
    (root / "usercache.json").write_text(json.dumps([{"name": "Conhecido", "uuid": real}]))

    MinecraftProvider().apply_player_action(root, PlayerAction.ALLOW_ADD, "Conhecido")
    entradas = {e["name"]: e["uuid"] for e in ler(root, "whitelist.json")}
    assert entradas["Conhecido"] == real


# ------------------------------------------- a decisao: console ou arquivo --


class FakePower:
    def __init__(self, estado):
        self.estado = estado
        self.comandos = []

    def state(self, instance):
        return self.estado

    async def send_command(self, instance, command):
        self.comandos.append(command)


class FakeBus:
    async def publish(self, *a, **k):
        pass


class FakeRegistry:
    def __init__(self, provider):
        self._p = provider

    def get(self, _id):
        return self._p


def servico(root, estado):
    power = FakePower(estado)
    svc = PlayerService(FakeRegistry(MinecraftProvider()), power, FakeBus())
    inst = Instance(id="i1", name="Srv", provider_id="minecraft", root_dir=str(root))
    return svc, inst, power


def test_offline_rodando_grava_arquivo_com_uuid_correto_e_recarrega(tmp_path):
    """Regressão do bug que barrava o dono do próprio servidor.

    Num servidor offline no ar, `whitelist add` resolveria o UUID pela Mojang —
    diferente do UUID offline com que o cliente entra. Então grava pelo arquivo
    (UUID offline certo) e manda `whitelist reload`, sem `whitelist add`.
    """
    root = montar(tmp_path, online_mode="false")
    svc, inst, power = servico(root, InstanceState.RUNNING)

    via = asyncio.run(svc.apply(inst, PlayerAction.ALLOW_ADD, "Fulano"))

    assert via == "recarga"
    assert power.comandos == ["whitelist reload"]  # e NÃO "whitelist add Fulano"
    entradas = {e["name"]: e["uuid"] for e in ler(root, "whitelist.json")}
    assert entradas["Fulano"] == offline_uuid("Fulano")


def test_online_rodando_usa_console(tmp_path):
    """Em online-mode o console resolve o UUID real da Mojang — que é o certo
    para o cliente online. Aí o caminho é o console, sem tocar no arquivo."""
    root = montar(tmp_path, online_mode="true")
    svc, inst, power = servico(root, InstanceState.RUNNING)

    via = asyncio.run(svc.apply(inst, PlayerAction.ALLOW_ADD, "Fulano"))

    assert via == "console"
    assert power.comandos == ["whitelist add Fulano"]
    assert [e["name"] for e in ler(root, "whitelist.json")] == ["edu"]  # intacto


def test_com_servidor_parado_grava_o_arquivo(tmp_path):
    root = montar(tmp_path)
    svc, inst, power = servico(root, InstanceState.STOPPED)

    via = asyncio.run(svc.apply(inst, PlayerAction.ALLOW_ADD, "Fulano"))

    assert via == "arquivo"
    assert power.comandos == []
    assert "Fulano" in [e["name"] for e in ler(root, "whitelist.json")]


def test_kick_exige_servidor_rodando(tmp_path):
    root = montar(tmp_path)
    svc, inst, _ = servico(root, InstanceState.STOPPED)
    with pytest.raises(ValidationFailedError, match="rodando"):
        asyncio.run(svc.apply(inst, PlayerAction.KICK, "edu"))


def test_kick_com_servidor_rodando_manda_motivo(tmp_path):
    root = montar(tmp_path)
    svc, inst, power = servico(root, InstanceState.RUNNING)
    asyncio.run(svc.apply(inst, PlayerAction.KICK, "edu", "volte depois"))
    assert power.comandos == ["kick edu volte depois"]


def test_nome_vazio_e_recusado(tmp_path):
    root = montar(tmp_path)
    svc, inst, _ = servico(root, InstanceState.RUNNING)
    with pytest.raises(ValidationFailedError):
        asyncio.run(svc.apply(inst, PlayerAction.ALLOW_ADD, "   "))


# -------------------------------------------- plano com o servidor no ar --


def test_live_plan_offline_whitelist_recarrega(tmp_path):
    root = montar(tmp_path, online_mode="false")
    assert player_live_plan(root, PlayerAction.ALLOW_ADD) == "whitelist reload"


def test_live_plan_offline_op_e_ban_gravam_sem_recarga(tmp_path):
    """ops.json e banned-players.json não têm recarga ao vivo no vanilla: o
    arquivo fica certo, aplica no próximo start."""
    root = montar(tmp_path, online_mode="false")
    assert player_live_plan(root, PlayerAction.ADMIN_ADD) == ""
    assert player_live_plan(root, PlayerAction.BAN) == ""


def test_live_plan_online_usa_console(tmp_path):
    root = montar(tmp_path, online_mode="true")
    assert player_live_plan(root, PlayerAction.ALLOW_ADD) is None
    assert player_live_plan(root, PlayerAction.ADMIN_ADD) is None
    assert player_live_plan(root, PlayerAction.BAN) is None


def test_live_plan_remocoes_sempre_pelo_console(tmp_path):
    """Remover/desbanir/deop/kick operam por nome — o console acerta nos dois
    modos, então nunca desviam para o arquivo."""
    root = montar(tmp_path, online_mode="false")
    for acao in (
        PlayerAction.ALLOW_REMOVE,
        PlayerAction.ADMIN_REMOVE,
        PlayerAction.UNBAN,
        PlayerAction.KICK,
    ):
        assert player_live_plan(root, acao) is None
