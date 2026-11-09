"""Config flow for the NAD (TCP) integration."""

from typing import Any, override

import probatio
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from pynadtcp import VOLUME_MAX_DB, VOLUME_MIN_DB, NadClient

from .const import (
    CONF_MAX_VOLUME,
    CONF_MIN_VOLUME,
    DEFAULT_MAX_VOLUME,
    DEFAULT_MIN_VOLUME,
    DOMAIN,
    NAD_EXCEPTIONS,
)

STEP_USER_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})

_VOLUME_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=VOLUME_MIN_DB,
        max=VOLUME_MAX_DB,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="dB",
    )
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_MIN_VOLUME): _VOLUME_SELECTOR,
        probatio.Required(CONF_MAX_VOLUME): _VOLUME_SELECTOR,
    }
)


class NadTcpOptionsFlow(OptionsFlowWithReload):
    """Handle the volume window options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the minimum and maximum volume."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # The number selector returns floats; whole dB values are what the amp uses.
            user_input = {key: int(value) for key, value in user_input.items()}
            if user_input[CONF_MIN_VOLUME] >= user_input[CONF_MAX_VOLUME]:
                errors["base"] = "invalid_volume_range"
            else:
                return self.async_create_entry(data=user_input)

        current = {
            CONF_MIN_VOLUME: DEFAULT_MIN_VOLUME,
            CONF_MAX_VOLUME: DEFAULT_MAX_VOLUME,
            **self.config_entry.options,
            **(user_input or {}),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, current),
            errors=errors,
        )


class NadTcpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NAD (TCP)."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> NadTcpOptionsFlow:
        """Return the options flow."""
        return NadTcpOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self.source != SOURCE_RECONFIGURE:
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            client = NadClient(user_input[CONF_HOST])
            try:
                await client.connect()
            except NAD_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={CONF_HOST: user_input[CONF_HOST]},
                    )
                return self.async_create_entry(
                    title=client.state.model or "NAD Amplifier",
                    data={CONF_HOST: user_input[CONF_HOST]},
                )
            finally:
                await client.disconnect()

        step_id = "reconfigure" if self.source == SOURCE_RECONFIGURE else "user"
        return self.async_show_form(
            step_id=step_id, data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        return await self.async_step_user(user_input)
