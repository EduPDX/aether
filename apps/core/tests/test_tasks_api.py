"""API de tarefas agendadas."""

from conftest import create_instance


def _criar(client, iid, **body):
    base = {"kind": "restart", "schedule": "daily", "at_hour": 4, "at_minute": 0}
    base.update(body)
    return client.post(f"/api/v1/instances/{iid}/tasks", json=base)


def test_task_roundtrip(client, mods_dir):
    iid = create_instance(client, mods_dir)
    assert client.get(f"/api/v1/instances/{iid}/tasks").json() == []

    res = _criar(client, iid, warn_minutes=5)
    assert res.status_code == 201, res.text
    t = res.json()
    assert t["description"] == "reiniciar o servidor, todo dia às 04:00"
    assert t["enabled"] is True
    assert t["last_run"] is None

    lista = client.get(f"/api/v1/instances/{iid}/tasks").json()
    assert [x["id"] for x in lista] == [t["id"]]

    # desliga
    res = client.put(
        f"/api/v1/instances/{iid}/tasks/{t['id']}",
        json={"kind": "restart", "schedule": "daily", "at_hour": 6, "enabled": False},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    assert "06:00" in res.json()["description"]

    assert client.delete(f"/api/v1/instances/{iid}/tasks/{t['id']}").status_code == 204
    assert client.get(f"/api/v1/instances/{iid}/tasks").json() == []


def test_dangerous_command_is_refused_by_the_api(client, mods_dir):
    iid = create_instance(client, mods_dir)
    res = _criar(client, iid, kind="command", command="stop")
    assert res.status_code == 400
    assert "reinício" in res.json()["detail"]


def test_empty_command_is_refused(client, mods_dir):
    iid = create_instance(client, mods_dir)
    assert _criar(client, iid, kind="command", command="   ").status_code == 400


def test_out_of_range_hour_is_refused(client, mods_dir):
    iid = create_instance(client, mods_dir)
    assert _criar(client, iid, at_hour=25).status_code == 422


def test_task_of_another_instance_is_not_reachable(client, mods_dir, tmp_path):
    """Id válido não pode dar acesso à tarefa de outra instância."""
    outra = tmp_path / "outra"
    outra.mkdir()
    iid_a = create_instance(client, mods_dir, "A")
    iid_b = create_instance(client, outra, "B")
    tarefa = _criar(client, iid_a).json()

    assert client.delete(f"/api/v1/instances/{iid_b}/tasks/{tarefa['id']}").status_code == 404
    res = client.put(
        f"/api/v1/instances/{iid_b}/tasks/{tarefa['id']}",
        json={"kind": "restart", "schedule": "daily"},
    )
    assert res.status_code == 404


def test_command_on_a_stopped_server_is_refused(client, mods_dir):
    """Enviar comando com o servidor parado não tem para onde ir."""
    iid = create_instance(client, mods_dir)
    tarefa = _criar(client, iid, kind="command", command="say oi").json()

    res = client.post(f"/api/v1/instances/{iid}/tasks/{tarefa['id']}/run")
    assert res.status_code == 400
    assert "no ar" in res.json()["detail"]


def test_scheduler_runs_a_due_task_and_marks_it(client, mods_dir, monkeypatch):
    """Integração: o laço do agendador realmente dispara e marca a execução.

    Sem marcar, o ciclo tentaria de novo a cada minuto dentro da janela.
    """
    import asyncio
    from datetime import datetime

    from aether_core.application.tasks import TaskService
    from aether_core.domain.tasks import ScheduledTask, TaskKind, TaskSchedule
    from aether_core.infrastructure.repositories import SqlScheduledTaskRepository

    iid = create_instance(client, mods_dir)
    app = client.app

    executadas: list[str] = []

    class _PowerFalso:
        async def restart(self, instance):
            executadas.append(instance.id)

    class _SupervisorParado:
        def state(self, _):
            from aether_core.domain.instances import InstanceState

            return InstanceState.STOPPED

        async def send_command(self, *_):
            raise AssertionError("servidor parado não recebe comando")

    async def cenario():
        async with app.state.session_factory() as session:
            repo = SqlScheduledTaskRepository(session)
            agora = datetime(2026, 7, 19, 4, 0)
            await repo.add(
                ScheduledTask.new(
                    instance_id=iid,
                    kind=TaskKind.RESTART,
                    schedule=TaskSchedule.DAILY,
                    at_hour=4,
                    at_minute=0,
                )
            )
            servico = TaskService(repo, _SupervisorParado(), _PowerFalso(), app.state.bus)

            vencidas = await servico.due_tasks(agora)
            assert len(vencidas) == 1, "a tarefa das 4h deve estar vencida às 4h"

            from aether_core.application.instances import InstanceService
            from aether_core.infrastructure.repositories import SqlInstanceRepository

            instancias = InstanceService(
                repo=SqlInstanceRepository(session),
                providers=app.state.providers,
                fs=app.state.fs,
                bus=app.state.bus,
            )
            instancia = await instancias.get(iid)
            await servico.run_now(instancia, vencidas[0])
            await servico.mark_run(vencidas[0], agora)

            # marcada: não roda de novo na mesma janela
            assert await servico.due_tasks(agora) == []

    asyncio.run(cenario())
    assert executadas == [iid], "o reinício foi de fato disparado"
