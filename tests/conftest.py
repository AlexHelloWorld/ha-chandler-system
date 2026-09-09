"""Fixtures for Chandler Water System tests."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(autouse=True)
def mock_bluetooth_history(mock_bluetooth_adapters):
    """Stub the adapter history, which otherwise needs a live D-Bus."""
    with patch("bluetooth_adapters.systems.linux.LinuxAdapters.history", {}):
        yield
