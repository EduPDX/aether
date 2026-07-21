"""Troca de versão do Minecraft: manifesto da Mojang, versão atual e fixar."""

import asyncio

from aether_provider_minecraft.server.versions import (
    current_version,
    fetch_versions,
    is_modded,
    pin_version,
)

# Recorte do manifesto real da Mojang.
MANIFESTO = {
    "latest": {"release": "1.21.1", "snapshot": "24w33a"},
    "versions": [
        {"id": "1.21.1", "type": "release"},
        {"id": "24w33a", "type": "snapshot"},
        {"id": "1.20.1", "type": "release"},
        {"id": "b1.7.3", "type": "old_beta"},
        {"id": "", "type": "release"},  # sem id: ignorada
    ],
}


def test_fetch_versions_separa_release_de_snapshot():
    async def http(_url):
        return MANIFESTO

    versoes = asyncio.run(fetch_versions(http))
    por_id = {v.id: v for v in versoes}

    assert por_id["1.21.1"].stable is True
    assert por_id["1.20.1"].stable is True
    assert por_id["24w33a"].stable is False
    assert por_id["24w33a"].description == "snapshot"
    assert por_id["b1.7.3"].stable is False
    assert "" not in por_id  # id vazio descartado


def test_fetch_versions_degrada_sem_quebrar():
    """Origem fora do ar não pode esvaziar a tela com exceção."""

    async def http_quebrado(_url):
        raise RuntimeError("sem rede")

    assert asyncio.run(fetch_versions(http_quebrado)) == []
    assert asyncio.run(fetch_versions(None)) == []


def test_current_version_le_do_container():
    pd = {"container": {"type": "FORGE", "version": "1.20.1"}}
    assert current_version(pd) == "1.20.1"
    assert current_version({}) == ""


def test_is_modded_conta_arquivos_nao_o_loader(tmp_path):
    """O aviso é sobre ter mod, não sobre o tipo do servidor: um Forge sem mod
    atualiza sem quebrar nada."""
    # servidor sem pasta de mods: não modado
    assert is_modded(tmp_path) is False

    # pasta de mods vazia: ainda não modado
    (tmp_path / "mods").mkdir()
    assert is_modded(tmp_path) is False

    # só um mod desabilitado: não carrega, não conta
    (tmp_path / "mods" / "algum.jar.disabled").write_text("x")
    assert is_modded(tmp_path) is False

    # um mod habilitado: modado
    (tmp_path / "mods" / "create.jar").write_text("x")
    assert is_modded(tmp_path) is True


def test_is_modded_pega_mods_do_cliente(tmp_path):
    """Mod só no perfil do cliente também conta — quebra ao trocar a versão."""
    (tmp_path / "aether-client" / "mods").mkdir(parents=True)
    (tmp_path / "aether-client" / "mods" / "sodium.jar").write_text("x")
    assert is_modded(tmp_path) is True


def test_pin_version_troca_so_a_versao_preservando_o_resto():
    pd = {"container": {"type": "FORGE", "version": "1.20.1", "memory": "10G", "port": 25565}}
    mudancas = pin_version(pd, "1.21.1")

    c = mudancas["container"]
    assert c["version"] == "1.21.1"
    # tipo, memória e porta intactos
    assert c["type"] == "FORGE"
    assert c["memory"] == "10G"
    assert c["port"] == 25565
    # não mexe no original
    assert pd["container"]["version"] == "1.20.1"


def test_pin_version_recusa_vazio():
    import pytest

    with pytest.raises(ValueError, match="versão"):
        pin_version({"container": {}}, "   ")
