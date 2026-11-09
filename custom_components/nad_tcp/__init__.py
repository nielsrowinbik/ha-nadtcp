"""The NAD (TCP) integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pynadtcp import NadClient

from .const import DOMAIN, LOGGER, NAD_EXCEPTIONS

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type NadConfigEntry = ConfigEntry[NadClient]


async def async_setup_entry(hass: HomeAssistant, entry: NadConfigEntry) -> bool:
    """Set up NAD (TCP) from a config entry."""
    client = NadClient(entry.data[CONF_HOST])
    try:
        await client.connect()
    except NAD_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err

    entry.runtime_data = client

    was_connected = True

    async def _log_connection_state(_client: NadClient) -> None:
        """Log once when the device drops off the network and once when it returns."""
        nonlocal was_connected
        connected = _client.is_connected()
        if connected == was_connected:
            return
        was_connected = connected
        if connected:
            LOGGER.warning("Reconnected to NAD amplifier at %s", entry.data[CONF_HOST])
        else:
            LOGGER.warning(
                "Lost connection to NAD amplifier at %s", entry.data[CONF_HOST]
            )

    # Unsubscribe on unload, so disconnecting on a reload doesn't log "Lost connection".
    entry.async_on_unload(client.register_state_update_callback(_log_connection_state))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NadConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.disconnect()
    return unload_ok
