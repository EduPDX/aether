"""End-to-end power tests using a fake server process (real subprocess).

The fake server is a Python script that emits Minecraft-like log lines,
echoes stdin and exits gracefully on ``stop`` — exercising the whole
pipeline: launch spec (custom command) → supervisor → codec → logs → WS.
"""

import sys
import time

FAKE_SERVER = """\
import sys
print('[00:00:00] [Server thread/INFO]: Starting minecraft server', flush=True)
print('[00:00:01] [Server thread/INFO]: Done (1.234s)! For help, type "help"', flush=True)
for line in sys.stdin:
    cmd = line.strip()
    print(f'[00:00:02] [Server thread/INFO]: echo {cmd}', flush=True)
    if cmd == 'stop':
        print('[00:00:03] [Server thread/INFO]: Stopping server', flush=True)
        break
"""

CRASHING_SERVER = """\
import sys
print('[00:00:00] [Server thread/ERROR]: something went terribly wrong', flush=True)
sys.exit(3)
"""


def create_server_instance(client, tmp_path, script: str, name: str = "Fake") -> str:
    (tmp_path / "eula.txt").write_text("eula=true")
    res = client.post(
        "/api/v1/instances",
        json={
            "name": name,
            "provider_id": "minecraft",
            "root_dir": str(tmp_path),
            "provider_data": {"command": [sys.executable, "-u", "-c", script]},
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def wait_state(client, iid: str, expected: str, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    state = ""
    while time.time() < deadline:
        state = client.get(f"/api/v1/instances/{iid}/status").json()["state"]
        if state == expected:
            return state
        time.sleep(0.1)
    return state


def test_full_lifecycle(client, tmp_path):
    iid = create_server_instance(client, tmp_path, FAKE_SERVER)

    res = client.post(f"/api/v1/instances/{iid}/power", json={"action": "start"})
    assert res.status_code == 200

    assert wait_state(client, iid, "running") == "running"

    logs = client.get(f"/api/v1/instances/{iid}/logs").json()["lines"]
    assert any("Done (1.234s)!" in line for line in logs)

    res = client.post(f"/api/v1/instances/{iid}/command", json={"command": "say hello"})
    assert res.status_code == 204
    time.sleep(0.5)
    logs = client.get(f"/api/v1/instances/{iid}/logs").json()["lines"]
    assert any("echo say hello" in line for line in logs)

    res = client.post(f"/api/v1/instances/{iid}/power", json={"action": "stop"})
    assert res.status_code == 200
    assert wait_state(client, iid, "stopped") == "stopped"


def test_start_twice_conflicts(client, tmp_path):
    iid = create_server_instance(client, tmp_path, FAKE_SERVER)
    client.post(f"/api/v1/instances/{iid}/power", json={"action": "start"})
    wait_state(client, iid, "running")

    res = client.post(f"/api/v1/instances/{iid}/power", json={"action": "start"})
    assert res.status_code == 409

    res = client.delete(f"/api/v1/instances/{iid}")
    assert res.status_code == 409  # running instances cannot be removed

    client.post(f"/api/v1/instances/{iid}/power", json={"action": "stop"})
    wait_state(client, iid, "stopped")


def test_crash_detected(client, tmp_path):
    iid = create_server_instance(client, tmp_path, CRASHING_SERVER)
    client.post(f"/api/v1/instances/{iid}/power", json={"action": "start"})
    assert wait_state(client, iid, "crashed") == "crashed"


def test_start_without_server_fails(client, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    res = client.post(
        "/api/v1/instances",
        json={"name": "Empty", "provider_id": "minecraft", "root_dir": str(empty)},
    )
    iid = res.json()["id"]
    res = client.post(f"/api/v1/instances/{iid}/power", json={"action": "start"})
    assert res.status_code == 400
    assert "no runnable server" in res.json()["detail"]


def test_websocket_streams_console_and_state(client, tmp_path):
    iid = create_server_instance(client, tmp_path, FAKE_SERVER)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"op": "subscribe", "topic": f"instance.{iid}"})
        client.post(f"/api/v1/instances/{iid}/power", json={"action": "start"})

        got_console = got_running = False
        for _ in range(20):
            msg = ws.receive_json()
            if msg["topic"].endswith(".console") and "Done" in msg["payload"]["line"]:
                got_console = True
            if msg["topic"].endswith(".state") and msg["payload"]["state"] == "running":
                got_running = True
            if got_console and got_running:
                break
        assert got_console and got_running

    client.post(f"/api/v1/instances/{iid}/power", json={"action": "stop"})
    wait_state(client, iid, "stopped")
