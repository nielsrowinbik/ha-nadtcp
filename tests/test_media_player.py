"""Tests for the NAD (TCP) media player."""

from dataclasses import replace
from unittest.mock import AsyncMock, create_autospec, patch

import pytest
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pynadtcp import NadClient, NadConnectionError, NadState
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.nad_tcp.const import CONF_MAX_VOLUME, CONF_MIN_VOLUME, DOMAIN

from . import mock_state_update, setup_integration
from .const import ENTITY_ID, TEST_HOST


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the media player entity against a snapshot."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player reflects the device state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes[ATTR_INPUT_SOURCE] == "Stream"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == mock_nad_client.sources


async def test_state_updates(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pushed state updates are reflected."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # An update while powered on is reflected in the attributes.
    mock_nad_client.state = NadState(
        power=True,
        volume_db=-27.5,
        muted=True,
        source="Phono",
        model="NADC338",
        version="1.53",
    )
    await mock_state_update(mock_nad_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.75
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert state.attributes[ATTR_INPUT_SOURCE] == "Phono"

    # Powering off is reflected in the state.
    mock_nad_client.state = NadState(power=False, model="NADC338", version="1.53")
    await mock_state_update(mock_nad_client)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    ("service", "service_data", "method", "call_args"),
    [
        (SERVICE_TURN_ON, {}, "power_on", ()),
        (SERVICE_TURN_OFF, {}, "power_off", ()),
        (SERVICE_VOLUME_UP, {}, "volume_up", ()),
        (SERVICE_VOLUME_DOWN, {}, "volume_down", ()),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.5}, "set_volume", (-45.0,)),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, "set_mute", (True,)),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "Phono"},
            "select_source",
            ("Phono",),
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, object],
    method: str,
    call_args: tuple[object, ...],
) -> None:
    """Test media player services call the library client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    getattr(mock_nad_client, method).assert_awaited_once_with(*call_args)


async def test_command_error(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A library error during a command surfaces as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    mock_nad_client.power_on.side_effect = NadConnectionError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


async def test_unknown_state_and_missing_volume(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """State is unknown without power info; volume is omitted when unset."""
    mock_nad_client.state = NadState(model="NADC338", version="1.53")
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    mock_nad_client.state = NadState(power=True, model="NADC338", version="1.53")
    await mock_state_update(mock_nad_client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert ATTR_MEDIA_VOLUME_LEVEL not in state.attributes


def _entry_with_window(
    entry: MockConfigEntry, min_volume: int, max_volume: int
) -> MockConfigEntry:
    """Return a copy of the entry with a volume window in its options."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=entry.title,
        data=dict(entry.data),
        entry_id=entry.entry_id,
        options={CONF_MIN_VOLUME: min_volume, CONF_MAX_VOLUME: max_volume},
    )


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    """Call a media player service on the test entity."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("window", "volume_db", "expected"),
    [
        (None, -80.0, 0.0),
        (None, -45.0, 0.5),
        (None, -10.0, 1.0),
        # Set from the remote beyond the window: clamped, not out of range.
        (None, -5.0, 1.0),
        ((-70, -20), -75.0, 0.0),
        ((-70, -20), -45.0, 0.5),
        ((-80, 0), -40.0, 0.5),
    ],
)
async def test_volume_level_window(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    window: tuple[int, int] | None,
    volume_db: float,
    expected: float,
) -> None:
    """The amp's dB is mapped onto 0..1 within the volume window."""
    if window is not None:
        mock_config_entry = _entry_with_window(mock_config_entry, *window)
    mock_nad_client.state = replace(mock_nad_client.state, volume_db=volume_db)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == expected


@pytest.mark.parametrize(
    ("window", "level", "expected_db"),
    [
        (None, 0.0, -80.0),
        (None, 1.0, -10.0),
        ((-70, -20), 0.5, -45.0),
        # Bug 1: the window edges at the device limits must not raise.
        ((-80, 0), 0.0, -80.0),
        ((-80, 0), 1.0, 0.0),
    ],
)
async def test_set_volume_level_window(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    window: tuple[int, int] | None,
    level: float,
    expected_db: float,
) -> None:
    """A 0..1 level is converted to dB within the volume window."""
    if window is not None:
        mock_config_entry = _entry_with_window(mock_config_entry, *window)
    await setup_integration(hass, mock_config_entry)

    await _call(hass, SERVICE_VOLUME_SET, **{ATTR_MEDIA_VOLUME_LEVEL: level})

    mock_nad_client.set_volume.assert_awaited_once_with(expected_db)


@pytest.mark.parametrize(
    ("window", "volume_db"),
    [
        # Bug 1: the old code sent -82 at the default floor and raised ValueError.
        (None, -80.0),
        (None, -85.0),
        ((-80, 0), -80.0),
        ((-60, -20), -60.0),
    ],
)
async def test_volume_down_at_floor(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    window: tuple[int, int] | None,
    volume_db: float,
) -> None:
    """Volume down at or below the minimum sends nothing and doesn't raise."""
    if window is not None:
        mock_config_entry = _entry_with_window(mock_config_entry, *window)
    mock_nad_client.state = replace(mock_nad_client.state, volume_db=volume_db)
    await setup_integration(hass, mock_config_entry)

    await _call(hass, SERVICE_VOLUME_DOWN)

    mock_nad_client.volume_down.assert_not_awaited()
    mock_nad_client.set_volume.assert_not_awaited()


@pytest.mark.parametrize(
    ("window", "volume_db"),
    [
        # Bug 2: amp set above max from the remote; the old code sent -8 (lower).
        (None, -5.0),
        (None, -10.0),
        ((-80, 0), 0.0),
    ],
)
async def test_volume_up_at_ceiling(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    window: tuple[int, int] | None,
    volume_db: float,
) -> None:
    """Volume up at or above the maximum sends nothing."""
    if window is not None:
        mock_config_entry = _entry_with_window(mock_config_entry, *window)
    mock_nad_client.state = replace(mock_nad_client.state, volume_db=volume_db)
    await setup_integration(hass, mock_config_entry)

    await _call(hass, SERVICE_VOLUME_UP)

    mock_nad_client.volume_up.assert_not_awaited()
    mock_nad_client.set_volume.assert_not_awaited()


@pytest.mark.parametrize("volume_db", [-40.0, None])
@pytest.mark.parametrize(
    ("service", "method"),
    [(SERVICE_VOLUME_UP, "volume_up"), (SERVICE_VOLUME_DOWN, "volume_down")],
)
async def test_volume_step_uses_native_step(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    volume_db: float | None,
    service: str,
    method: str,
) -> None:
    """Bug 2 and 3: inside the window (or when unknown), step with the amp's own +/-."""
    mock_nad_client.state = replace(mock_nad_client.state, volume_db=volume_db)
    await setup_integration(hass, mock_config_entry)

    await _call(hass, service)

    getattr(mock_nad_client, method).assert_awaited_once_with()
    mock_nad_client.set_volume.assert_not_awaited()


async def test_unique_id_is_entry_id(
    hass: HomeAssistant,
    mock_nad_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Bug 7: the unique ID is the config entry ID, not the IP address."""
    await setup_integration(hass, mock_config_entry)

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == mock_config_entry.entry_id
    assert TEST_HOST not in entity.unique_id


async def test_two_amplifiers_are_independent(hass: HomeAssistant) -> None:
    """Bug 4: an update from one amplifier only changes its own entity."""
    clients = []
    for host, model in (("192.168.1.50", "NADC338"), ("192.168.1.51", "NADC338")):
        client = create_autospec(NadClient, instance=True)
        client.host = host
        client.state = NadState(
            power=True, volume_db=-45.0, muted=False, source="Stream", model=model
        )
        client.sources = ["Stream", "Phono"]
        client.is_connected.return_value = True
        clients.append(client)
    living_room = MockConfigEntry(
        domain=DOMAIN, title="Living room", data={CONF_HOST: "192.168.1.50"}
    )
    kitchen = MockConfigEntry(
        domain=DOMAIN, title="Kitchen", data={CONF_HOST: "192.168.1.51"}
    )

    with patch("custom_components.nad_tcp.NadClient", side_effect=clients):
        await setup_integration(hass, living_room)
        await setup_integration(hass, kitchen)

    clients[0].state = replace(clients[0].state, source="Phono", volume_db=-10.0)
    await mock_state_update(clients[0])
    await hass.async_block_till_done()

    living = hass.states.get("media_player.living_room")
    other = hass.states.get("media_player.kitchen")
    assert living.attributes[ATTR_INPUT_SOURCE] == "Phono"
    assert living.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert other.attributes[ATTR_INPUT_SOURCE] == "Stream"
    assert other.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
