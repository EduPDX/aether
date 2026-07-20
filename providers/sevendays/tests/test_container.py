"""Spec de container e provision do 7 Days to Die."""

from pathlib import Path

from aether_provider_sevendays.server.container import (
    DEFAULT_PORT,
    build_container_spec,
    provision,
    provision_schema,
)
from aether_provider_sevendays.server.serverconfig import ServerConfigXmlCodec
from aether_sdk import LaunchContext


def test_spec_expoe_portas_do_jogo_e_steam():
    spec = build_container_spec(LaunchContext(root_dir=Path("."), provider_data={}))
    portas = {(p.container_port, p.protocol) for p in spec.ports}
    assert (26900, "tcp") in portas
    assert (26900, "udp") in portas
    assert (26901, "udp") in portas


def test_porta_do_provider_data_vira_host_port():
    spec = build_container_spec(
        LaunchContext(root_dir=Path("."), provider_data={"container": {"port": 27000}})
    )
    principal = next(p for p in spec.ports if p.container_port == DEFAULT_PORT)
    assert principal.host_port == 27000


def test_steamcmd_forca_a_plataforma_linux_antes_do_login():
    """O 294420 é um app do tipo "Tool": sem `+@sSteamCmdForcePlatformType
    linux` o SteamCMD aborta com "Missing configuration" e não baixa nada.
    A flag precisa vir antes do +login para valer."""
    spec = build_container_spec(LaunchContext(root_dir=Path("."), provider_data={}))
    script = spec.command[-1]
    assert "+@sSteamCmdForcePlatformType linux" in script
    assert script.index("+@sSteamCmdForcePlatformType") < script.index("+login")


def test_roda_como_usuario_steam_nao_como_root():
    """SteamCMD como root morre com "Missing file permissions"; a imagem traz
    o usuário steam (uid 1000) exatamente para isso."""
    spec = build_container_spec(LaunchContext(root_dir=Path("."), provider_data={}))
    assert spec.run_as == "1000:1000"


def test_volume_unico_cobre_a_raiz():
    """Servidor, config e saves moram todos no root da instância — é o que
    faz files/backup/config enxergarem o mesmo disco que o jogo."""
    spec = build_container_spec(LaunchContext(root_dir=Path("."), provider_data={}))
    assert [(v.container_path, v.subdir) for v in spec.volumes] == [("/data", ".")]


def test_provision_escreve_config_e_estrutura(tmp_path):
    data = provision(tmp_path, {"ServerName": "Meu 7DTD", "GameWorld": "RWG"})
    values = ServerConfigXmlCodec().parse((tmp_path / "serverconfig.xml").read_text())
    assert values["ServerName"] == "Meu 7DTD"
    assert values["GameWorld"] == "RWG"
    assert (tmp_path / "server").is_dir()
    assert (tmp_path / "UserData").is_dir()
    assert data["container"]["port"] == DEFAULT_PORT


def test_schema_de_provision_esconde_avancados():
    assert all(not f.advanced for f in provision_schema().fields)
