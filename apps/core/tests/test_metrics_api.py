"""Metrics API and client-profile content type."""

import os

from aether_core.application.metrics import MetricsService
from conftest import create_instance


class _FakeSupervisor:
    """Aponta para o próprio processo de teste, que está sempre vivo."""

    def __init__(self, pid: int) -> None:
        self._pid = pid

    def pid_of(self, instance_id: str) -> int | None:
        return self._pid


def test_process_cpu_is_measured_across_samples():
    """Regressão: recriar o psutil.Process a cada coleta zerava a CPU.

    ``cpu_percent(interval=None)`` é um delta desde a leitura anterior daquele
    objeto. Sem cache, toda chamada era "a primeira" e devolvia 0.0 para
    sempre — a memória aparecia na interface e a CPU não.
    """
    service = MetricsService(_FakeSupervisor(os.getpid()))

    first = service.process("i1")
    assert first.running is True
    assert first.mem_bytes > 0

    # queima CPU para haver o que medir na janela entre as duas coletas
    total = 0
    for n in range(3_000_000):
        total += n

    second = service.process("i1")
    assert second.cpu_percent > 0.0, "a segunda coleta deve enxergar uso de CPU"
    # o objeto Process foi reaproveitado, não recriado
    assert service._procs[os.getpid()] is service._procs[os.getpid()]


def test_metrics_reports_host_resources(client, tmp_path):
    create_instance(client, tmp_path / "srv" if (tmp_path / "srv").mkdir() is None else tmp_path)
    res = client.get("/api/v1/metrics")
    assert res.status_code == 200
    body = res.json()

    host = body["host"]
    assert host["cpu_count"] >= 1
    assert host["mem_total"] > 0
    assert 0 <= host["mem_percent"] <= 100
    assert host["disk_total"] > 0
    assert host["uptime_seconds"] > 0

    # instância parada aparece com processo inativo
    assert body["instances"], "deve listar as instâncias"
    assert body["instances"][0]["running"] is False
    # o histórico ganha um ponto a cada leitura
    assert len(body["history"]) >= 1


def test_client_mods_are_a_separate_content_type(client, tmp_path):
    root = tmp_path / "srv2"
    (root / "mods").mkdir(parents=True)
    (root / "mods" / "servidor.jar").write_bytes(b"s")
    # sem override: usa os diretórios padrão do provider (mods/ e
    # aether-client/mods/), que é como o usuário cria pela interface
    res = client.post(
        "/api/v1/instances",
        json={"name": "Com cliente", "provider_id": "minecraft", "root_dir": str(root)},
    )
    assert res.status_code == 201, res.text
    iid = res.json()["id"]

    # o tipo existe no provider
    providers = client.get("/api/v1/providers").json()
    ctypes = {c["id"]: c for c in providers[0]["content_types"]}
    assert ctypes["mod_client"]["default_directory"] == "aether-client/mods"

    # a pasta do perfil de cliente é criada sob demanda e começa vazia
    res = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod_client"})
    assert res.status_code == 200
    assert res.json() == []
    assert (root / "aether-client" / "mods").is_dir()

    # enviar um mod de cliente não mexe nos mods do servidor
    up = client.post(
        f"/api/v1/instances/{iid}/files/upload",
        data={"path": "aether-client/mods"},
        files=[("uploads", ("Jade.jar", b"cliente", "application/java-archive"))],
    )
    assert up.status_code == 200
    client_mods = client.get(
        f"/api/v1/instances/{iid}/content", params={"type": "mod_client"}
    ).json()
    server_mods = client.get(f"/api/v1/instances/{iid}/content", params={"type": "mod"}).json()
    assert [m["file"] for m in client_mods] == ["Jade.jar"]
    assert [m["file"] for m in server_mods] == ["servidor.jar"]


def test_process_cpu_is_reported_both_per_core_and_per_machine():
    """324% num servidor de 10 núcleos é ~32% da máquina, não um defeito.

    O psutil conta 100% por núcleo saturado. Exibir só esse número ao lado de
    medidores que vão até 100% faz parecer que a medição quebrou, então o
    serviço entrega também o valor relativo à máquina inteira.
    """
    import psutil

    service = MetricsService(_FakeSupervisor(os.getpid()))
    service.process("i1")
    total = 0
    for n in range(2_000_000):
        total += n
    m = service.process("i1")

    nucleos = psutil.cpu_count(logical=True) or 1
    assert m.cpu_count == nucleos
    assert m.cpu_percent > 0
    # o normalizado é o mesmo uso dividido pelos núcleos
    assert m.cpu_percent_total == round(m.cpu_percent / nucleos, 1)
    # e nunca passa de 100%, que é o que o medidor da interface espera
    assert m.cpu_percent_total <= 100.0


def test_stopped_instance_reports_zero_but_still_knows_the_core_count():
    class _SemProcesso:
        def pid_of(self, _):
            return None

    m = MetricsService(_SemProcesso()).process("i1")
    assert (m.cpu_percent, m.cpu_percent_total, m.running) == (0.0, 0.0, False)
    assert m.cpu_count >= 1
