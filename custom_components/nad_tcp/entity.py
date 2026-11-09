"""Base entity for the NAD (TCP) integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate, override

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from pynadtcp import NadClient

from .const import DOMAIN, NAD_EXCEPTIONS

if TYPE_CHECKING:
    from . import NadConfigEntry


def command[_EntityT: NadEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Wrap a command method to translate library errors into HA errors."""

    @wraps(func)
    async def _wrapper(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except NAD_EXCEPTIONS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"entity_id": self.entity_id},
            ) from err

    return _wrapper


class NadEntity(Entity):
    """Base entity for a NAD amplifier."""

    _attr_has_entity_name = True

    def __init__(self, client: NadClient, entry: NadConfigEntry) -> None:
        """Initialize the entity."""
        self.client = client
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="NAD",
            model=client.state.model,
            sw_version=client.state.version,
        )
        self._unsubscribe: Callable[[], None] | None = None

    async def _state_update_callback(self, _client: NadClient) -> None:
        """Handle state updates pushed from the device."""
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return True if the device connection is alive."""
        return self.client.is_connected()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to device updates."""
        self._unsubscribe = self.client.register_state_update_callback(
            self._state_update_callback
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device updates."""
        if self._unsubscribe is not None:
            self._unsubscribe()
