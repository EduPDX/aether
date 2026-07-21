"""HumanitZ: container, instalação, contrato e o codec do GameServerSettings.ini."""

from pathlib import Path

from aether_provider_humanitz import provider
from aether_provider_humanitz.server.container import (
    DEFAULT_PORT,
    DEFAULT_QUERY_PORT,
    LAUNCHER,
    build_container_spec,
    provision,
)
from aether_provider_humanitz.server.serversettings import (
    GameServerIniCodec,
    config_warnings,
    seed,
)
from aether_sdk import (
    LaunchContext,
    SupportsConfig,
    SupportsContainer,
    SupportsInstall,
    SupportsInstallSize,
    SupportsProvision,
)

FIXTURES = Path(__file__).parent / "fixtures"
REF = (FIXTURES / "REF_GameServerSettings.ini").read_text(encoding="utf-8")


def instalado(tmp_path: Path) -> Path:
    (tmp_path / "server").mkdir(exist_ok=True)
    (tmp_path / "server" / LAUNCHER).write_text("#!/bin/sh\n")
    return tmp_path


def spec_de(tmp_path: Path, provider_data: dict | None = None):
    return build_container_spec(
        LaunchContext(root_dir=instalado(tmp_path), provider_data=provider_data or {})
    )


# --------------------------------------------------------------------- contrato
def test_provider_satisfaz_os_contratos():
    assert isinstance(provider, SupportsContainer)
    assert isinstance(provider, SupportsInstall)
    assert isinstance(provider, SupportsInstallSize)
    assert isinstance(provider, SupportsProvision)
    assert isinstance(provider, SupportsConfig)


# -------------------------------------------------------------------- container
def test_sem_o_jogo_instalado_nao_ha_o_que_subir(tmp_path):
    assert build_container_spec(LaunchContext(root_dir=tmp_path, provider_data={})) is None


def test_boot_roda_o_launcher_com_portas(tmp_path):
    script = spec_de(tmp_path).command[-1]
    assert LAUNCHER in script
    assert "steamcmd" not in script
    assert "-queryport=" in script


def test_expoe_porta_do_jogo_e_de_consulta(tmp_path):
    portas = {(p.container_port, p.protocol) for p in spec_de(tmp_path).ports}
    assert (DEFAULT_PORT, "udp") in portas
    assert (DEFAULT_QUERY_PORT, "udp") in portas


def test_provider_data_ajusta_portas_e_nome(tmp_path):
    spec = spec_de(
        tmp_path, {"container": {"port": 8000, "query_port": 8001, "steam_name": "Do Dario"}}
    )
    assert spec.env["AETHER_PORT"] == "8000"
    assert spec.env["AETHER_QUERY_PORT"] == "8001"
    assert spec.env["AETHER_STEAM_NAME"] == "Do Dario"


def test_install_padrao_usa_a_branch_linux():
    """A public do HumanitZ só tem binários de Windows; o servidor Linux está
    na linuxbranch. Sem versão escolhida, é ela que deve ser baixada."""
    script = provider.install_spec(LaunchContext(root_dir=Path("."), provider_data={}), "").command[
        -1
    ]
    assert "app_update 2728330" in script
    assert "-beta linuxbranch" in script


def test_versoes_escondem_branches_de_windows():
    dump = (
        '"branches"\n{\n'
        '\t\t\t"public"\n\t\t\t{\n\t\t\t\t"buildid"\t\t"1"\n\t\t\t}\n'
        '\t\t\t"linuxbranch"\n\t\t\t{\n\t\t\t\t"buildid"\t\t"2"\n\t\t\t}\n'
        '\t\t\t"windowsbranch"\n\t\t\t{\n\t\t\t\t"buildid"\t\t"3"\n\t\t\t}\n'
        "}\n"
    )
    ids = {v.id for v in provider.parse_versions(dump)}
    assert ids == {"linuxbranch"}
    linux = provider.parse_versions(dump)[0]
    assert linux.stable is True and "Linux" in linux.label


# ------------------------------------------------------------------------ codec
def test_parse_le_chaves_ativas_sem_aspas():
    valores = GameServerIniCodec().parse(REF)
    assert valores["ServerName"] == "HumanitZ [Dedicated]"
    assert valores["MaxPlayers"] == "16"
    assert valores["PVP"] == "false"


def test_apply_preserva_comentarios_secoes_e_aspas():
    novo = GameServerIniCodec().apply(REF, {"ServerName": "Servidor do Dario", "MaxPlayers": "24"})
    # valor com aspas continua com aspas; valor sem aspas continua sem
    assert 'ServerName="Servidor do Dario"' in novo
    assert "MaxPlayers=24" in novo
    # comentários e seções intactos
    assert "[World Settings]" in novo
    assert ";Server name. Avoid using the word" in novo
    # não inventa chave que a versão não tem
    assert "Inexistente" not in GameServerIniCodec().apply(REF, {"Inexistente": "x"})


def test_comentario_com_chave_nao_e_alterado():
    """Uma linha comentada que contém uma chave conhecida não pode ser tocada."""
    texto = ";MaxPlayers=999 <- exemplo\nMaxPlayers=16\n"
    novo = GameServerIniCodec().apply(texto, {"MaxPlayers": "20"})
    assert ";MaxPlayers=999 <- exemplo" in novo
    assert "MaxPlayers=20" in novo


# ------------------------------------------------------------------------- seed
def test_seed_copia_do_arquivo_de_referencia_e_aplica(tmp_path):
    ref = tmp_path / "server" / "HumanitZServer" / "REF_GameServerSettings.ini"
    ref.parent.mkdir(parents=True)
    ref.write_text(REF, encoding="utf-8")

    criou = seed(tmp_path, {"ServerName": "Meu HumanitZ", "PVP": "true"})

    ativo = tmp_path / "server" / "HumanitZServer" / "GameServerSettings.ini"
    valores = GameServerIniCodec().parse(ativo.read_text())
    assert criou is True
    assert valores["ServerName"] == "Meu HumanitZ"
    assert valores["PVP"] == "true"
    # partiu do arquivo do jogo, não de um gerado: as outras chaves seguem lá
    assert valores["SaveIntervalSec"] == "300"


def test_seed_nao_sobrescreve_config_existente(tmp_path):
    ref = tmp_path / "server" / "HumanitZServer" / "REF_GameServerSettings.ini"
    ref.parent.mkdir(parents=True)
    ref.write_text(REF, encoding="utf-8")
    ativo = tmp_path / "server" / "HumanitZServer" / "GameServerSettings.ini"
    ativo.write_text('ServerName="Config do usuário"\n', encoding="utf-8")

    criou = seed(tmp_path, {})

    assert criou is False
    assert "Config do usuário" in ativo.read_text()


def test_after_install_prepara_config_e_limpa_pendencias(tmp_path):
    ref = tmp_path / "server" / "HumanitZServer" / "REF_GameServerSettings.ini"
    ref.parent.mkdir(parents=True)
    ref.write_text(REF, encoding="utf-8")

    mudancas = provider.after_install(tmp_path, {"pending_config": {"ServerName": "Do Dario"}})

    ativo = tmp_path / "server" / "HumanitZServer" / "GameServerSettings.ini"
    valores = GameServerIniCodec().parse(ativo.read_text())
    assert valores["ServerName"] == "Do Dario"
    assert mudancas["pending_config"] == {}
    assert mudancas["install"]["config_seeded"] is True


# ---------------------------------------------------------------------- avisos
def test_avisa_sobre_nome_com_official(tmp_path):
    avisos = config_warnings(tmp_path, {"ServerName": "Official Server BR"})
    assert avisos and avisos[0].level == "error"


# -------------------------------------------------------------------- provision
def test_provision_guarda_escolhas_e_nome_de_steam(tmp_path):
    data = provision(tmp_path, {"ServerName": "Meu HumanitZ", "MaxPlayers": "24"})
    assert data["pending_config"]["ServerName"] == "Meu HumanitZ"
    assert data["container"]["steam_name"] == "Meu HumanitZ"
    assert data["container"]["port"] == DEFAULT_PORT


def test_provision_schema_esconde_avancados():
    assert all(not f.advanced for f in provider.provision_schema().fields)
