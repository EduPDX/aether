from aether_provider_minecraft.server.status import player_names


def test_nomes_distinguem_lista_oculta_de_servidor_vazio():
    assert player_names({"online": 2}) == {"names": None, "names_complete": False}
    assert player_names({"online": 0}) == {"names": [], "names_complete": True}


def test_amostra_filtra_texto_de_plugins_e_nao_promete_lista_completa():
    players = {
        "online": 3,
        "sample": [
            {"name": "Edu_PDX"},
            {"name": "Edu_PDX"},
            {"name": "Bem-vindo ao servidor!"},
            None,
        ],
    }
    assert player_names(players) == {"names": ["Edu_PDX"], "names_complete": False}
    assert player_names({"online": 1, "sample": [{"name": "Edu_PDX"}]}) == {
        "names": ["Edu_PDX"],
        "names_complete": True,
    }
