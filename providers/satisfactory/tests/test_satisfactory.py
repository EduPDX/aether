"""Satisfactory: container, instalação e contrato do provider."""

from pathlib import Path

from aether_provider_satisfactory import provider
from aether_provider_satisfactory.server.container import (
    DEFAULT_PORT,
    LAUNCHER,
    build_container_spec,
    provision,
)
from aether_sdk import (
    LaunchContext,
    SupportsContainer,
    SupportsInstall,
    SupportsInstallSize,
    SupportsProvision,
)


def instalado(tmp_path: Path) -> Path:
    (tmp_path / "server").mkdir(exist_ok=True)
    (tmp_path / "server" / LAUNCHER).write_text("#!/bin/sh\n")
    return tmp_path


def spec_de(tmp_path: Path, provider_data: dict | None = None):
    return build_container_spec(
        LaunchContext(root_dir=instalado(tmp_path), provider_data=provider_data or {})
    )


def test_provider_satisfaz_os_contratos_de_criacao():
    assert isinstance(provider, SupportsContainer)
    assert isinstance(provider, SupportsInstall)
    assert isinstance(provider, SupportsInstallSize)
    assert isinstance(provider, SupportsProvision)


def test_sem_o_jogo_instalado_nao_ha_o_que_subir(tmp_path):
    spec = build_container_spec(LaunchContext(root_dir=tmp_path, provider_data={}))
    assert spec is None


def test_boot_roda_o_launcher_e_nao_o_steamcmd(tmp_path):
    script = spec_de(tmp_path).command[-1]
    assert LAUNCHER in script
    assert "steamcmd" not in script


def test_porta_unica_tcp_e_udp(tmp_path):
    portas = {(p.container_port, p.protocol) for p in spec_de(tmp_path).ports}
    assert (DEFAULT_PORT, "tcp") in portas
    assert (DEFAULT_PORT, "udp") in portas


def test_porta_do_provider_data_vira_host_port(tmp_path):
    spec = spec_de(tmp_path, {"container": {"port": 8888}})
    assert all(p.host_port == 8888 for p in spec.ports)
    # e é passada ao processo pelo ambiente, não hardcoded no comando
    assert spec.env["AETHER_PORT"] == "8888"


def test_install_spec_baixa_o_app_do_servidor():
    script = provider.install_spec(
        LaunchContext(root_dir=Path("."), provider_data={}), "public"
    ).command[-1]
    assert "app_update 1690800" in script
    assert "+@sSteamCmdForcePlatformType linux" in script


def test_provision_nao_tem_campos_de_jogo():
    """Satisfactory se configura no jogo, não em arquivo: a criação não pede
    nada além do nome da instância."""
    assert provider.provision_schema().fields == []


def test_provision_cria_a_pasta_do_servidor(tmp_path):
    data = provision(tmp_path, {})
    assert (tmp_path / "server").is_dir()
    assert data["container"]["port"] == DEFAULT_PORT


def test_installed_version_le_o_manifesto(tmp_path):
    steamapps = tmp_path / "server" / "steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "appmanifest_1690800.acf").write_text('"buildid"\t\t"23300422"\n')
    assert provider.installed_version(tmp_path) == "23300422"
