"""Test Springwell Water Softener integration initialization."""
import pytest

from custom_components.springwell_softener.const import DOMAIN


async def test_domain_constant():
    """Test that the domain constant is set correctly."""
    assert DOMAIN == "springwell_softener"

