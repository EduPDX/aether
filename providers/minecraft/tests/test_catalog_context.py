"""Tradução do provider_data em (versão, loader) para filtrar o catálogo.

Regressão de um bug real: o catálogo baixava mod de qualquer versão porque a
versão e o loader da instância nunca chegavam ao filtro — a provisão os grava
em `container`, a detecção em `game`, e o Core lia um terceiro nome vazio.
"""

from aether_provider_minecraft.server.game_meta import catalog_context


def test_instancia_provisionada_forge():
    """Servidor criado do zero: dados no bloco container, tipo em maiúsculo.

    É o caso exato que quebrou em produção — FORGE 1.20.1 baixando Create de
    NeoForge 1.21.1.
    """
    pd = {"container": {"type": "FORGE", "version": "1.20.1", "memory": "10G"}}
    assert catalog_context(pd) == ("1.20.1", "forge")


def test_instancia_provisionada_fabric():
    pd = {"container": {"type": "FABRIC", "version": "1.21.1"}}
    assert catalog_context(pd) == ("1.21.1", "fabric")


def test_vanilla_nao_filtra_por_loader():
    """Vanilla não carrega jar de mod; filtrar por loader não faz sentido."""
    pd = {"container": {"type": "VANILLA", "version": "1.20.4"}}
    assert catalog_context(pd) == ("1.20.4", None)


def test_latest_nao_e_versao_concreta():
    """LATEST só se resolve quando o servidor sobe — não filtra a busca."""
    pd = {"container": {"type": "FABRIC", "version": "LATEST"}}
    assert catalog_context(pd) == (None, "fabric")


def test_instancia_adotada_usa_o_bloco_game():
    """Pasta existente: versão e loader vêm da detecção dos arquivos."""
    pd = {"game": {"minecraft": "1.19.2", "loader": "neoforge"}}
    assert catalog_context(pd) == ("1.19.2", "neoforge")


def test_adotada_vanilla_detectada_nao_filtra_loader():
    pd = {"game": {"minecraft": "1.20.1", "loader": "vanilla"}}
    assert catalog_context(pd) == ("1.20.1", None)


def test_container_tem_prioridade_sobre_game():
    """Se os dois blocos existirem, o container (escolha explícita) vence."""
    pd = {
        "container": {"type": "FORGE", "version": "1.20.1"},
        "game": {"minecraft": "1.7.10", "loader": "fabric"},
    }
    assert catalog_context(pd) == ("1.20.1", "forge")


def test_sem_dados_nao_filtra():
    assert catalog_context({}) == (None, None)
    assert catalog_context(None) == (None, None)
