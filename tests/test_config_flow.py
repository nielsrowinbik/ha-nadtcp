"""Tests for the NAD (TCP) config flow."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pynadtcp import NadConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nad_tcp.const import CONF_MAX_VOLUME, CONF_MIN_VOLUME, DOMAIN

from . import setup_integration
from .const import TEST_HOST


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_nad_client: AsyncMock) -> None:
    """Test the full user flow succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NADC338"
    assert result["data"] == {CONF_HOST: TEST_HOST}
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_cannot_connect(
    hass: HomeAssistant, mock_nad_client: AsyncMock
) -> None:
    """Test the flow recovers from a connection error."""
    mock_nad_client.connect.side_effect = NadConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_nad_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: TEST_HOST}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_host_aborts(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that configuring the same host twice aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring updates the host and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.99"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.99"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow surfaces a connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_nad_client.connect.side_effect = NadConnectionError

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.99"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test saving the volume window stores options and reloads the entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_nad_client.connect.await_count == 1

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MIN_VOLUME: -70, CONF_MAX_VOLUME: -20}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_MIN_VOLUME: -70, CONF_MAX_VOLUME: -20}
    assert all(type(value) is int for value in mock_config_entry.options.values())
    assert CONF_MIN_VOLUME not in mock_config_entry.data
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_nad_client.connect.await_count == 2


@pytest.mark.parametrize(("min_volume", "max_volume"), [(-20, -20), (-10, -30)])
async def test_options_flow_invalid_range(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    min_volume: int,
    max_volume: int,
) -> None:
    """Test a minimum at or above the maximum is rejected."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MIN_VOLUME: min_volume, CONF_MAX_VOLUME: max_volume}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_volume_range"}
    assert mock_config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MIN_VOLUME: -60, CONF_MAX_VOLUME: -10}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_MIN_VOLUME: -60, CONF_MAX_VOLUME: -10}


async def test_options_flow_out_of_bounds(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test values outside the amplifier's -80..0 dB range are rejected."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_MIN_VOLUME: -90, CONF_MAX_VOLUME: 5}
        )
