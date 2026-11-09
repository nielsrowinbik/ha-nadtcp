"""Tests for the NAD (TCP) integration."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the NAD (TCP) integration in Home Assistant."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def mock_state_update(client: AsyncMock) -> None:
    """Replay the registered state-update callbacks."""
    for call in client.register_state_update_callback.call_args_list:
        await call[0][0](client)
