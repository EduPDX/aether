"""O provider de 7 Days to Die deve passar a suíte genérica do SDK."""

from aether_provider_sevendays import provider
from aether_sdk.testing import check_provider_contract


def test_provider_satisfies_contract():
    assert check_provider_contract(provider) == []
