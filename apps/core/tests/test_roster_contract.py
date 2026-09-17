from types import SimpleNamespace

from aether_core.application.live_status import _CACHE, live_players


def test_status_preserva_nomes_sem_exigir_capability_de_outros_providers():
    try:
        _CACHE.clear()
        provider = SimpleNamespace(
            live_status=lambda host, port: {
                "online": 2,
                "max": 20,
                "names": ["Jogador"],
                "names_complete": False,
            }
        )
        assert live_players(provider, 25565) == {
            "online": 2,
            "max": 20,
            "names": ["Jogador"],
            "names_complete": False,
        }
        _CACHE.clear()
        provider = SimpleNamespace(live_status=lambda host, port: {"online": 2, "max": 20})
        assert live_players(provider, 25565) == {"online": 2, "max": 20}
    finally:
        _CACHE.clear()
