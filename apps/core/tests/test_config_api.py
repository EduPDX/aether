"""Schema-driven config API tests."""

from conftest import create_instance

PROPERTIES = """\
#Minecraft server properties
#Thu Jul 16 2026
motd=Meu servidor
max-players=20
difficulty=normal
pvp=true
online-mode=false
"""


def make_instance(client, tmp_path):
    root = tmp_path / "srv"
    root.mkdir()
    (root / "server.properties").write_text(PROPERTIES, encoding="utf-8", newline="\n")
    return create_instance(client, root), root


def test_list_configs_reads_values(client, tmp_path):
    iid, _ = make_instance(client, tmp_path)
    res = client.get(f"/api/v1/instances/{iid}/config")
    assert res.status_code == 200
    configs = res.json()
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg["schema"]["id"] == "server-properties"
    assert cfg["file_exists"] is True
    assert cfg["values"]["motd"] == "Meu servidor"
    assert cfg["values"]["pvp"] == "true"
    field_keys = [f["key"] for f in cfg["schema"]["fields"]]
    assert "difficulty" in field_keys


def test_update_preserves_comments_and_unknown_keys(client, tmp_path):
    iid, root = make_instance(client, tmp_path)
    res = client.put(
        f"/api/v1/instances/{iid}/config",
        json={
            "schema_id": "server-properties",
            "values": {"motd": "Aether!", "max-players": "40", "white-list": "true"},
        },
    )
    assert res.status_code == 204

    text = root.joinpath("server.properties").read_text()
    assert "#Minecraft server properties" in text  # comentário preservado
    assert "motd=Aether!" in text
    assert "max-players=40" in text
    assert "online-mode=false" in text  # chave não enviada permanece
    assert "white-list=true" in text  # chave nova adicionada


def test_update_rejects_unknown_keys(client, tmp_path):
    """Só chaves declaradas no schema podem ser gravadas.

    Sem isso, um cliente escreveria qualquer coisa no server.properties.
    """
    iid, _ = make_instance(client, tmp_path)
    res = client.put(
        f"/api/v1/instances/{iid}/config",
        json={"schema_id": "server-properties", "values": {"nao-existe-no-schema": "x"}},
    )
    assert res.status_code == 400


def test_password_fields_are_declared_as_such(client, tmp_path):
    """A senha do RCON não pode ser renderizada em texto claro."""
    iid, _ = make_instance(client, tmp_path)
    schemas = client.get(f"/api/v1/instances/{iid}/config").json()
    campos = {f["key"]: f for s in schemas for f in s["schema"]["fields"]}

    assert campos["rcon.password"]["type"] == "password"
    # e continua sendo gravável, agora que faz parte do schema
    res = client.put(
        f"/api/v1/instances/{iid}/config",
        json={"schema_id": "server-properties", "values": {"rcon.password": "segredo"}},
    )
    assert res.status_code == 204


def test_missing_file_returns_empty_values(client, tmp_path):
    root = tmp_path / "vazio"
    root.mkdir()
    iid = create_instance(client, root)
    cfg = client.get(f"/api/v1/instances/{iid}/config").json()[0]
    assert cfg["file_exists"] is False
    assert cfg["values"] == {}
