"""The Minecraft provider must pass the generic SDK contract suite."""

from aether_provider_minecraft import provider
from aether_sdk.testing import check_provider_contract


def test_provider_satisfies_contract():
    assert check_provider_contract(provider) == []
