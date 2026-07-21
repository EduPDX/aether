"""Infra compartilhada do SDK: comando do SteamCMD e console da Unreal Engine."""

from pathlib import Path

from aether_sdk import steamcmd
from aether_sdk.console_ue import UnrealConsoleCodec


# --------------------------------------------------------------------- steamcmd
def test_forca_a_plataforma_linux_antes_do_login():
    """Apps de servidor dedicado são do tipo Tool: sem a flag antes do +login o
    SteamCMD aborta com 'Missing configuration' e não baixa nada."""
    script = steamcmd.install_spec(1690800, "public").command[-1]
    assert "+@sSteamCmdForcePlatformType linux" in script
    assert script.index("+@sSteamCmdForcePlatformType") < script.index("+login")


def test_branch_padrao_nao_usa_beta():
    assert "-beta" not in steamcmd.install_spec(2728330, "public").command[-1]


def test_branch_especifica_vira_beta():
    script = steamcmd.install_spec(2728330, "experimental").command[-1]
    assert "-beta experimental" in script


def test_roda_sem_root_e_com_home():
    spec = steamcmd.install_spec(1690800, "public")
    assert spec.run_as == "1000:1000"
    assert spec.env["HOME"] == "/home/steam"


def test_parse_branches_marca_experimental_como_instavel():
    dump = (
        '"branches"\n{\n'
        '\t\t\t"public"\n\t\t\t{\n\t\t\t\t"buildid"\t\t"100"\n\t\t\t}\n'
        '\t\t\t"experimental"\n\t\t\t{\n\t\t\t\t"buildid"\t\t"101"\n\t\t\t}\n'
        "}\n"
    )
    por_id = {v.id: v for v in steamcmd.parse_branches(dump)}
    assert por_id["public"].stable is True
    assert por_id["public"].label == "Mais recente (estável)"
    assert por_id["experimental"].stable is False


def test_parse_branches_vazio_nao_levanta():
    assert steamcmd.parse_branches("") == []
    assert steamcmd.parse_branches("steam fora do ar") == []


def test_installed_build_le_o_manifesto(tmp_path):
    steamapps = tmp_path / "server" / "steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "appmanifest_1690800.acf").write_text('"buildid"\t\t"23300422"\n')
    assert steamcmd.installed_build(tmp_path, 1690800) == "23300422"
    assert steamcmd.installed_build(tmp_path, 999) == ""


def test_installed_build_vazio_sem_instalacao(tmp_path):
    assert steamcmd.installed_build(Path(tmp_path), 1690800) == ""


# ------------------------------------------------------------------- console UE
def test_console_ue_extrai_categoria_e_severidade():
    codec = UnrealConsoleCodec()
    linha = codec.parse("[2026.07.21-12.00.05:123][  0]LogNet: Warning: perdeu pacote")
    assert linha.level == "WARN"
    assert linha.message == "LogNet: perdeu pacote"


def test_console_ue_info_por_padrao():
    codec = UnrealConsoleCodec()
    assert codec.parse("[2026.07.21-12.00.05:123][  5]LogGame: autosave").level == "INFO"


def test_console_ue_linha_fora_do_formato_passa_crua():
    codec = UnrealConsoleCodec()
    linha = codec.parse("Redirecting stderr to log")
    assert linha.message == "Redirecting stderr to log"


def test_console_ue_marca_pronto_pelo_padrao():
    codec = UnrealConsoleCodec(ready_pattern=r"is ready")
    assert codec.parse("[..][ 0]LogServer: World is ready").ready is True
    assert codec.parse("[..][ 0]LogServer: still loading").ready is False
