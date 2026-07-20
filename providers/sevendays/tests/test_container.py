"""Spec do container que roda o servidor e o provisionamento da instância."""

from pathlib import Path

from aether_provider_sevendays.server.container import (
    BINARIO,
    DEFAULT_PORT,
    build_container_spec,
    provision,
    provision_schema,
)
from aether_sdk import LaunchContext


def instalado(tmp_path: Path) -> Path:
    """Simula o jogo já instalado pela fase de instalação."""
    (tmp_path / "server").mkdir(exist_ok=True)
    (tmp_path / "server" / BINARIO).write_text("#!/bin/sh\n")
    return tmp_path


def spec_de(tmp_path: Path, provider_data: dict | None = None):
    return build_container_spec(
        LaunchContext(root_dir=instalado(tmp_path), provider_data=provider_data or {})
    )


def test_sem_o_jogo_instalado_nao_ha_o_que_subir(tmp_path):
    """Melhor recusar com clareza do que criar um container que morre com
    'no such file' — a instalação é uma fase própria e pode não ter rodado."""
    spec = build_container_spec(LaunchContext(root_dir=tmp_path, provider_data={}))
    assert spec is None


def test_boot_nao_chama_o_steamcmd(tmp_path):
    """Instalar no boot fazia toda subida falar com a Steam e impedia preparar
    a config antes do primeiro start."""
    script = spec_de(tmp_path).command[-1]
    assert "steamcmd" not in script
    assert BINARIO in script


def test_spec_expoe_portas_do_jogo_e_steam(tmp_path):
    portas = {(p.container_port, p.protocol) for p in spec_de(tmp_path).ports}
    assert (26900, "tcp") in portas
    assert (26900, "udp") in portas
    assert (26901, "udp") in portas


def test_porta_do_provider_data_vira_host_port(tmp_path):
    spec = spec_de(tmp_path, {"container": {"port": 27000}})
    principal = next(p for p in spec.ports if p.container_port == DEFAULT_PORT)
    assert principal.host_port == 27000


def test_roda_como_usuario_steam_nao_como_root(tmp_path):
    """SteamCMD como root morre com "Missing file permissions"; o servidor
    herda o mesmo usuário para escrever nos arquivos que ele instalou."""
    assert spec_de(tmp_path).run_as == "1000:1000"


def test_volume_unico_cobre_a_raiz(tmp_path):
    """Servidor, config e saves moram todos no root da instância — é o que
    faz arquivos/backup/config enxergarem o mesmo disco que o jogo."""
    spec = spec_de(tmp_path)
    assert [(v.container_path, v.subdir) for v in spec.volumes] == [("/data", ".")]


def test_provision_guarda_escolhas_sem_escrever_config(tmp_path):
    """O serverconfig.xml precisa ser cópia do arquivo da versão instalada, e
    nessa hora o jogo ainda não existe em disco. As respostas ficam pendentes
    até o after_install."""
    data = provision(tmp_path, {"ServerName": "Meu 7DTD", "GameWorld": "RWG"})

    assert not (tmp_path / "serverconfig.xml").exists()
    assert data["pending_config"]["ServerName"] == "Meu 7DTD"
    assert data["container"]["port"] == DEFAULT_PORT
    assert (tmp_path / "server").is_dir()
    assert (tmp_path / "UserData").is_dir()


def test_schema_de_provision_esconde_avancados():
    assert all(not f.advanced for f in provision_schema().fields)
