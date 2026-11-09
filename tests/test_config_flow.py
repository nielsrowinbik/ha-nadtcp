"""Tests for the NAD (TCP) config flow."""

import json
from fnmatch import fnmatch
from ipaddress import ip_address
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import (
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
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


CAST_ID = "bcb250cd21c2fc6482d40594a012e408"


def _zeroconf_info(
    host: str = TEST_HOST, **properties: str | None
) -> ZeroconfServiceInfo:
    """Return a Cast announcement as the C338 sends it."""
    props = {"id": CAST_ID, "md": "NAD Amplifier C338", "fn": "Amplifier"}
    props.update(properties)
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="bcb250cd-21c2-fc64-82d4-0594a012e408.local.",
        name=f"NAD-Amplifier-C338-{CAST_ID}._googlecast._tcp.local.",
        port=8009,
        type="_googlecast._tcp.local.",
        properties={key: value for key, value in props.items() if value is not None},
    )


def test_manifest_matches_c338() -> None:
    """The zeroconf matcher in the manifest matches the C338's Cast model name."""
    manifest = json.loads(
        (
            Path(__file__).parents[1] / "custom_components/nad_tcp/manifest.json"
        ).read_text()
    )
    (matcher,) = manifest["zeroconf"]
    assert matcher["type"] == "_googlecast._tcp.local."
    assert fnmatch("NAD Amplifier C338".lower(), matcher["properties"]["md"])
    assert not fnmatch("BRAVIA 4K UR3".lower(), matcher["properties"]["md"])


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(hass: HomeAssistant, mock_nad_client: AsyncMock) -> None:
    """A discovered amp is confirmed and named after its Cast friendly name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "Amplifier",
        "model": "NAD Amplifier C338",
        "host": TEST_HOST,
    }

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Amplifier"
    assert result["data"] == {CONF_HOST: TEST_HOST}
    assert result["result"].unique_id == CAST_ID
    mock_nad_client.disconnect.assert_awaited()


@pytest.mark.parametrize(
    ("properties", "expected_title"),
    [
        ({"fn": None}, "NAD Amplifier C338"),
        ({"fn": None, "md": None}, "NADC338"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_title_fallbacks(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    properties: dict[str, str | None],
    expected_title: str,
) -> None:
    """Without a friendly name, fall back to the Cast model, then the reported model."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info(**properties)
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["title"] == expected_title


async def test_zeroconf_not_nad_protocol(
    hass: HomeAssistant, mock_nad_client: AsyncMock
) -> None:
    """A NAD Cast device that doesn't answer on port 30001 is ignored."""
    mock_nad_client.connect.side_effect = NadConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_nad_client.disconnect.assert_awaited()


async def test_zeroconf_without_cast_id(
    hass: HomeAssistant, mock_nad_client: AsyncMock
) -> None:
    """An announcement without a Cast ID is not set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info(id=None)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
    mock_nad_client.connect.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_updates_host(
    hass: HomeAssistant, mock_nad_client: AsyncMock
) -> None:
    """A known amp discovered at a new address gets its host updated."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=CAST_ID, data={CONF_HOST: "192.168.1.99"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == TEST_HOST
    mock_nad_client.connect.assert_not_awaited()


async def test_zeroconf_adopts_entry_added_by_ip(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An entry added by IP address gets the Cast ID instead of a second offer."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.unique_id is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.unique_id == CAST_ID
    mock_nad_client.connect.assert_not_awaited()


async def test_zeroconf_ignores_entry_with_other_host(
    hass: HomeAssistant, mock_nad_client: AsyncMock
) -> None:
    """An entry added by IP address for another amp is left alone."""
    other = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.99"})
    other.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert other.unique_id is None


async def test_zeroconf_added_by_ip_while_waiting(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Confirming aborts if the same amp was added by IP address meanwhile."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf_info()
    )
    assert result["type"] is FlowResultType.FORM

    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
