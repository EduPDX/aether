"""Remoção de instância: o que sai do disco e o que fica.

O projeto não usa pytest-asyncio; os casos assíncronos rodam via asyncio.run.

O caso que originou estes testes: um servidor de 7 Days to Die e um de
Minecraft foram removidos pelo painel, mas o container e 17 GB de arquivos
continuaram no host.
"""

import asyncio
from pathlib import Path

from aether_core.application.ports import ManagedContainer
from aether_core.application.removal import InstanceRemover
from aether_core.domain.instances import Instance


class FakeRuntime:
    def __init__(self, containers: dict[str, str] | None = None) -> None:
        # container_id -> instance_id
        self.containers = dict(containers or {})
        self.removidos: list[str] = []

    async def list_managed(self):
        return [ManagedContainer(cid, iid, False) for cid, iid in self.containers.items()]

    async def remove(self, container_id: str) -> None:
        self.containers.pop(container_id, None)
        self.removidos.append(container_id)


class FakeSupervisor:
    def __init__(self) -> None:
        self.esquecidas: list[str] = []

    def forget(self, instance_id: str) -> None:
        self.esquecidas.append(instance_id)


def _ambiente(tmp_path: Path):
    instances_dir = tmp_path / "instances"
    backups_dir = tmp_path / "backups"
    instances_dir.mkdir()
    backups_dir.mkdir()
    return instances_dir, backups_dir


def _gerenciada(instances_dir: Path, nome: str = "abc123") -> Instance:
    raiz = instances_dir / nome
    (raiz / "server").mkdir(parents=True)
    (raiz / "server" / "jogo.bin").write_bytes(b"x" * 2048)
    return Instance.new("7DTD", "sevendays", str(raiz), runtime="docker")


def test_remove_container_e_pasta_da_instancia_gerenciada(tmp_path):
    """O bug que motivou tudo: remover deixava container e arquivos no host."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        instance = _gerenciada(instances_dir)
        runtime = FakeRuntime({"cid-1": instance.id})
        supervisor = FakeSupervisor()
        remover = InstanceRemover(instances_dir, backups_dir, runtime, supervisor)

        rel = await remover.remove(instance)

        assert rel.container_removido is True
        assert runtime.removidos == ["cid-1"]
        assert not Path(instance.root_dir).exists()
        assert rel.bytes_liberados >= 2048
        assert supervisor.esquecidas == [instance.id]
        assert rel.falhas == []

    asyncio.run(caso())


def test_pasta_adotada_nunca_e_apagada(tmp_path):
    """O servidor existia antes do painel e continua existindo depois dele —
    apagar a pasta do usuário seria destruir dado que não é nosso."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        adotada = tmp_path / "servidor-do-usuario"
        adotada.mkdir()
        (adotada / "mundo.dat").write_text("precioso")
        instance = Instance.new("MC", "minecraft", str(adotada))

        remover = InstanceRemover(instances_dir, backups_dir, FakeRuntime(), FakeSupervisor())
        rel = await remover.remove(instance)

        assert adotada.is_dir()
        assert (adotada / "mundo.dat").read_text() == "precioso"
        assert rel.pasta_preservada == str(adotada)
        assert rel.pasta_removida == ""

    asyncio.run(caso())


def test_backups_da_instancia_saem_junto(tmp_path):
    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        instance = _gerenciada(instances_dir)
        pasta = backups_dir / instance.id
        pasta.mkdir()
        (pasta / "backup-1.zip").write_bytes(b"z" * 512)
        (pasta / "backup-2.zip").write_bytes(b"z" * 512)

        remover = InstanceRemover(instances_dir, backups_dir, FakeRuntime(), FakeSupervisor())
        rel = await remover.remove(instance)

        assert rel.backups_removidos == 2
        assert not pasta.exists()

    asyncio.run(caso())


def test_container_de_outra_instancia_nao_e_tocado(tmp_path):
    """Remover um servidor não pode derrubar o do vizinho."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        alvo = _gerenciada(instances_dir, "alvo")
        vizinho = _gerenciada(instances_dir, "vizinho")
        runtime = FakeRuntime({"cid-alvo": alvo.id, "cid-vizinho": vizinho.id})

        remover = InstanceRemover(instances_dir, backups_dir, runtime, FakeSupervisor())
        await remover.remove(alvo)

        assert runtime.removidos == ["cid-alvo"]
        assert "cid-vizinho" in runtime.containers
        assert Path(vizinho.root_dir).is_dir()

    asyncio.run(caso())


def test_keep_files_preserva_os_dados(tmp_path):
    """Tirar do painel sem apagar o servidor é um pedido legítimo."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        instance = _gerenciada(instances_dir)
        runtime = FakeRuntime({"cid-1": instance.id})

        remover = InstanceRemover(instances_dir, backups_dir, runtime, FakeSupervisor())
        rel = await remover.remove(instance, apagar_dados=False)

        # O container é sempre nosso e sai; os arquivos ficam.
        assert rel.container_removido is True
        assert Path(instance.root_dir).is_dir()
        assert rel.pasta_preservada == instance.root_dir

    asyncio.run(caso())


def test_docker_indisponivel_nao_impede_a_remocao(tmp_path):
    """Sem Docker ainda dá para limpar o disco — e é justamente aí que o
    usuário mais precisa que a remoção funcione."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        instance = _gerenciada(instances_dir)

        class RuntimeQuebrado(FakeRuntime):
            async def list_managed(self):
                raise OSError("docker fora do ar")

        remover = InstanceRemover(instances_dir, backups_dir, RuntimeQuebrado(), FakeSupervisor())
        rel = await remover.remove(instance)

        assert rel.container_removido is False
        assert not Path(instance.root_dir).exists()

    asyncio.run(caso())


def test_falha_ao_remover_container_nao_impede_apagar_a_pasta(tmp_path):
    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        instance = _gerenciada(instances_dir)

        class RuntimeTeimoso(FakeRuntime):
            async def remove(self, container_id: str) -> None:
                raise OSError("container travado")

        runtime = RuntimeTeimoso({"cid-1": instance.id})
        remover = InstanceRemover(instances_dir, backups_dir, runtime, FakeSupervisor())
        rel = await remover.remove(instance)

        assert not Path(instance.root_dir).exists()
        assert any("container" in f for f in rel.falhas)

    asyncio.run(caso())


def test_instalacao_em_andamento_e_cancelada_antes_de_apagar(tmp_path):
    """Um download em curso recria a pasta logo depois de ela ser apagada, e a
    remoção "bem-sucedida" deixaria lixo para trás."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        instance = _gerenciada(instances_dir)

        class FakeInstalls:
            def __init__(self) -> None:
                self.canceladas: list[str] = []

            async def cancelar(self, instance_id: str) -> bool:
                self.canceladas.append(instance_id)
                return True

        installs = FakeInstalls()
        remover = InstanceRemover(
            instances_dir, backups_dir, FakeRuntime(), FakeSupervisor(), installs
        )
        rel = await remover.remove(instance)

        assert installs.canceladas == [instance.id]
        assert rel.instalacao_cancelada is True
        assert not Path(instance.root_dir).exists()

    asyncio.run(caso())


def test_varredura_remove_orfaos_de_remocoes_antigas(tmp_path):
    """Recupera o que já vazou antes desta correção existir."""

    async def caso():
        instances_dir, backups_dir = _ambiente(tmp_path)
        viva = _gerenciada(instances_dir, "viva")
        (instances_dir / "orfa-1").mkdir()
        (instances_dir / "orfa-2").mkdir()
        runtime = FakeRuntime({"cid-viva": viva.id, "cid-orfa": "sumida"})

        remover = InstanceRemover(instances_dir, backups_dir, runtime, FakeSupervisor())
        containers = await remover.limpar_containers_orfaos({viva.id})
        pastas = await remover.limpar_pastas_orfas({viva.id}, {str(Path(viva.root_dir).resolve())})

        assert containers == ["sumida"]
        assert runtime.removidos == ["cid-orfa"]
        assert len(pastas) == 2
        assert Path(viva.root_dir).is_dir()  # a viva não foi tocada

    asyncio.run(caso())
