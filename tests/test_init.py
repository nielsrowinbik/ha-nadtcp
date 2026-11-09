"""Tests for the NAD (TCP) integration setup."""

import logging
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pynadtcp import NadConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from custom_components.nad_tcp.const import DOMAIN

from . import mock_state_update, setup_integration


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_nad_client.disconnect.assert_awaited_once()


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry is retried when the device is unreachable."""
    mock_nad_client.connect.side_effect = NadConnectionError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_log_when_unavailable(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bug 6: one warning on disconnect, one on reconnect, nothing in between."""
    await setup_integration(hass, mock_config_entry)

    def _warnings() -> list[str]:
        return [
            r.getMessage()
            for r in caplog.records
            if r.name == "custom_components.nad_tcp" and r.levelno >= logging.WARNING
        ]

    caplog.clear()
    mock_nad_client.is_connected = Mock(return_value=False)
    for _ in range(3):
        await mock_state_update(mock_nad_client)
    assert _warnings() == [
        "Lost connection to NAD amplifier at 192.168.1.50",
    ]

    mock_nad_client.is_connected = Mock(return_value=True)
    for _ in range(3):
        await mock_state_update(mock_nad_client)
    assert _warnings() == [
        "Lost connection to NAD amplifier at 192.168.1.50",
        "Reconnected to NAD amplifier at 192.168.1.50",
    ]


async def test_unload_unsubscribes(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unloading drops every state callback, so the final disconnect logs nothing."""
    await setup_integration(hass, mock_config_entry)
    registrations = mock_nad_client.register_state_update_callback.call_count
    assert registrations == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unsubscribe = mock_nad_client.register_state_update_callback.return_value
    assert unsubscribe.call_count == registrations
