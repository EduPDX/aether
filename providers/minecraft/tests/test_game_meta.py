"""Detecção de versão/loader dos arquivos do servidor."""

from aether_provider_minecraft.server.game_meta import detect_game_metadata


def _forge_dir(root, mc, forge):
    d = root / "libraries" / "net" / "minecraftforge" / "forge" / f"{mc}-{forge}"
    d.mkdir(parents=True)
    (d / "marker").write_text("x")


def test_prefere_a_versao_configurada_e_nao_a_maior(tmp_path):
    """Regressão: trocar 1.20.1 → 26.2 e voltar deixa as duas instalações no
    disco. A detecção pegava a maior por nome (26.2) mesmo com o servidor de
    volta em 1.20.1, e o manifesto do sync saía com a versão errada."""
    _forge_dir(tmp_path, "1.20.1", "47.4.10")
    _forge_dir(tmp_path, "26.2", "65.0.6")

    pd = {"container": {"type": "FORGE", "version": "1.20.1"}}
    meta = detect_game_metadata(tmp_path, pd)
    assert meta == {"minecraft": "1.20.1", "loader": "forge", "loader_version": "47.4.10"}


def test_sem_versao_alvo_pega_a_mais_nova(tmp_path):
    """Pasta adotada (sem bloco container): mantém o comportamento de pegar a
    instalação mais recente."""
    _forge_dir(tmp_path, "1.20.1", "47.4.10")
    _forge_dir(tmp_path, "1.19.2", "43.0.0")

    meta = detect_game_metadata(tmp_path, {})
    assert meta["minecraft"] == "1.20.1"


def test_override_explicito_vence(tmp_path):
    _forge_dir(tmp_path, "1.20.1", "47.4.10")
    pd = {"game": {"minecraft": "1.7.10", "loader": "forge"}}
    assert detect_game_metadata(tmp_path, pd)["minecraft"] == "1.7.10"
