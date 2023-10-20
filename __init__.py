"""Awox light control"""

from __future__ import annotations

import logging


from .const import DOMAIN, CONF_MESH_NAME, CONF_MESH_PASSWORD, CONF_MESH_KEY

from .awox import AwoxMeshLight as awox

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant



PLATFORMS = [LIGHT_DOMAIN]

_LOGGER = logging.getLogger("awox")

ATTR_NAME = "name"
DEFAULT_NAME = "World"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Awox controller/hub specific code."""
    def handle_hello(call):
        """Handle the service call."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.set("awox.hello", name)

    hass.services.register(DOMAIN, "hello", handle_hello)


    # Data that you want to share with your platforms
    hass.states.async_set('awox.user', 'Andrea')

    hass.data[DOMAIN] = {}


    """Set up the an async service example component."""
    @callback
    def my_service(call: ServiceCall) -> None:
        """My first service."""
        _LOGGER.info('Received data', call.data)

    # Register our service with Home Assistant.
    hass.services.async_register(DOMAIN, 'light_switch', my_service)


    # Return boolean to indicate that initialization was successfully.
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up awox light via a config (flow) entry."""

    _LOGGER.info('setup config flow entry %s', entry.data)

    mesh = awox(hass, entry.data[CONF_MESH_NAME], entry.data[CONF_MESH_PASSWORD], entry.data[CONF_MESH_KEY])

    # Make `mesh` accessible for all platforms
    hass.data[DOMAIN][entry.entry_id] = mesh

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.info('Unload entry %s', entry.entry_id)
    if entry.entry_id in hass.data[DOMAIN]:
        await hass.data[DOMAIN][entry.entry_id].async_shutdown()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok