"""Instalação por versão: comando do SteamCMD, lista de branches e após-instalar.

O dump de branches da fixture é a saída real do `app_info_print` do app 294420.
"""

from pathlib import Path

from aether_provider_sevendays import provider
from aether_provider_sevendays.server.install import (
    install_spec,
    installed_version,
    parse_versions,
)
from aether_provider_sevendays.server.serverconfig import ServerConfigXmlCodec
from aether_sdk import LaunchContext

FIXTURES = Path(__file__).parent / "fixtures"
DUMP = (FIXTURES / "app_info_branches.txt").read_text(encoding="utf-8")
DISTRIBUIDO = (FIXTURES / "serverconfig-3.0.1.xml").read_text(encoding="utf-8")


def _script(version: str) -> str:
    return install_spec(LaunchContext(root_dir=Path("."), provider_data={}), version).command[-1]


def test_forca_a_plataforma_linux_antes_do_login():
    """O 294420 é um app do tipo "Tool": sem a flag o SteamCMD aborta com
    "Missing configuration" e não baixa nada. Precisa vir antes do +login."""
    script = _script("public")
    assert "+@sSteamCmdForcePlatformType linux" in script
    assert script.index("+@sSteamCmdForcePlatformType") < script.index("+login")


def test_versao_estavel_nao_usa_beta():
    """`-beta public` não é aceito: a branch padrão se pede pela ausência."""
    assert "-beta" not in _script("public")


def test_versao_especifica_vira_beta():
    script = _script("v2.6")
    assert "-beta v2.6" in script
    assert script.index("-beta") < script.index("validate")


def test_parse_versions_le_as_branches_reais():
    versoes = parse_versions(DUMP)
    por_id = {v.id: v for v in versoes}

    assert "public" in por_id
    assert "v3.0.1" in por_id
    assert por_id["v3.0.1"].description == "Version 3.0.1 Stable"
    assert por_id["v3.0.1"].build == "24117900"
    assert por_id["public"].label == "Mais recente (estável)"


def test_experimental_vem_marcada_como_instavel():
    """Entrar numa experimental sem querer é jeito clássico de quebrar um
    servidor em produção — a interface precisa poder separá-las."""
    por_id = {v.id: v for v in parse_versions(DUMP)}
    assert por_id["latest_experimental"].stable is False
    assert por_id["v3.0.1"].stable is True


def test_saida_invalida_nao_derruba_a_tela():
    assert parse_versions("") == []
    assert parse_versions("steamcmd fora do ar") == []


def test_installed_version_le_o_manifesto(tmp_path):
    steamapps = tmp_path / "server" / "steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "appmanifest_294420.acf").write_text('"buildid"\t\t"24117900"\n')
    assert installed_version(tmp_path) == "24117900"


def test_installed_version_vazia_sem_instalacao(tmp_path):
    assert installed_version(tmp_path) == ""


def test_after_install_prepara_config_e_limpa_pendencias(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "serverconfig.xml").write_text(DISTRIBUIDO, encoding="utf-8")

    mudancas = provider.after_install(
        tmp_path, {"pending_config": {"ServerName": "Servidor do Dario"}}
    )
    valores = ServerConfigXmlCodec().parse((tmp_path / "serverconfig.xml").read_text())

    assert valores["ServerName"] == "Servidor do Dario"
    assert len(valores) >= 68  # partiu do arquivo do jogo, não de um gerado
    assert mudancas["pending_config"] == {}  # não reaplica na próxima instalação
    assert mudancas["install"]["config_seeded"] is True
