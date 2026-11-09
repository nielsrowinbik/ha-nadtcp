"""Constants for the NAD (TCP) integration."""

import logging

from pynadtcp import NadConnectionError, NadTimeoutError

DOMAIN = "nad_tcp"

LOGGER = logging.getLogger(__package__)

NAD_EXCEPTIONS = (NadConnectionError, NadTimeoutError, TimeoutError)

CONF_MIN_VOLUME = "min_volume"
CONF_MAX_VOLUME = "max_volume"

DEFAULT_MIN_VOLUME = -80
DEFAULT_MAX_VOLUME = -10
