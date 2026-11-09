"""Fixtures for the NAD (TCP) tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import CONF_HOST
from pynadtcp import NadState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nad_tcp.const import DOMAIN

from .const import TEST_HOST

SOURCES = [
    "Stream",
    "Wireless",
    "TV",
    "Phono",
    "Coax1",
    "Coax2",
    "Opt1",
    "Opt2",
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the custom integration in every test."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.nad_tcp.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nad_client() -> Generator[AsyncMock]:
    """Mock a NAD client."""
    with (
        patch(
            "custom_components.nad_tcp.NadClient",
            autospec=True,
        ) as mock_client,
        patch(
            "custom_components.nad_tcp.config_flow.NadClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.host = TEST_HOST
        client.state = NadState(
            power=True,
            volume_db=-45.0,
            muted=False,
            source="Stream",
            model="NADC338",
            version="1.53",
        )
        client.sources = SOURCES
        client.is_connected = Mock(return_value=True)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NADC338",
        data={CONF_HOST: TEST_HOST},
        entry_id="01J5NADTCP00000000000000AB",
    )
