"""Media player platform for the NAD (TCP) integration."""

from typing import override

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pynadtcp import NadClient

from . import NadConfigEntry
from .const import (
    CONF_MAX_VOLUME,
    CONF_MIN_VOLUME,
    DEFAULT_MAX_VOLUME,
    DEFAULT_MIN_VOLUME,
)
from .entity import NadEntity, command

PARALLEL_UPDATES = 0

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NAD media player from a config entry."""
    async_add_entities([NadMediaPlayer(entry.runtime_data, entry)])


class NadMediaPlayer(NadEntity, MediaPlayerEntity):
    """Representation of a NAD amplifier as a media player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, client: NadClient, entry: NadConfigEntry) -> None:
        """Initialize the media player with the configured volume window."""
        super().__init__(client, entry)
        self._min_db: float = entry.options.get(CONF_MIN_VOLUME, DEFAULT_MIN_VOLUME)
        self._max_db: float = entry.options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the power state of the amplifier."""
        power = self.client.state.power
        if power is None:
            return None
        return MediaPlayerState.ON if power else MediaPlayerState.OFF

    @property
    @override
    def volume_level(self) -> float | None:
        """Return the volume level, mapping the volume window to 0..1."""
        volume_db = self.client.state.volume_db
        if volume_db is None:
            return None
        level = (volume_db - self._min_db) / (self._max_db - self._min_db)
        return min(1.0, max(0.0, level))

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Return whether the amplifier is muted."""
        return self.client.state.muted

    @property
    @override
    def source(self) -> str | None:
        """Return the current input source."""
        return self.client.state.source

    @property
    @override
    def source_list(self) -> list[str]:
        """Return the list of selectable input sources."""
        return self.client.sources

    @command
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level, converting 0..1 to the volume window."""
        await self.client.set_volume(
            self._min_db + volume * (self._max_db - self._min_db)
        )

    @command
    @override
    async def async_volume_up(self) -> None:
        """Step the volume up, unless already at or above the maximum."""
        volume_db = self.client.state.volume_db
        if volume_db is not None and volume_db >= self._max_db:
            return
        await self.client.volume_up()

    @command
    @override
    async def async_volume_down(self) -> None:
        """Step the volume down, unless already at or below the minimum."""
        volume_db = self.client.state.volume_db
        if volume_db is not None and volume_db <= self._min_db:
            return
        await self.client.volume_down()

    @command
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the amplifier."""
        await self.client.set_mute(mute)

    @command
    @override
    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self.client.select_source(source)

    @command
    @override
    async def async_turn_on(self) -> None:
        """Turn the amplifier on."""
        await self.client.power_on()

    @command
    @override
    async def async_turn_off(self) -> None:
        """Turn the amplifier off."""
        await self.client.power_off()
