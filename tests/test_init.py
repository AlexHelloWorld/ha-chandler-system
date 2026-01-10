"""Test Chandler Water System integration initialization."""
import pytest

from custom_components.chandler_system.const import DOMAIN


async def test_domain_constant():
    """Test that the domain constant is set correctly."""
    assert DOMAIN == "chandler_system"
