"""Awox light control"""

from __future__ import annotations

import logging


from .const import DOMAIN, CONF_MESH_NAME, CONF_MESH_PASSWORD, CONF_MESH_KEY

from .awox import AwoxMeshLight

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry

from homeassistant.components import bluetooth

PLATFORMS = [LIGHT_DOMAIN]

_LOGGER = logging.getLogger("awox")

ATTR_NAME = "name"
DEFAULT_NAME = "World"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Awox controller/hub specific code."""

    # Data that you want to share with your platforms
    hass.states.async_set('awox.user', 'Andrea')
    hass.states.async_set('awox.mac', "A4:C1:38:77:2A:18")
    
    
    bledevice = bluetooth.async_scanner_devices_by_address(hass , "A4:C1:38:77:2A:18" , connectable=True)
    _LOGGER.info('bledevice %s', bledevice)


    hass.data[DOMAIN] = {}




    # Return boolean to indicate that initialization was successfully.
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up awox light via a config (flow) entry."""

    _LOGGER.info('setup config flow entry %s', entry.data)
    _LOGGER.info('setup config flow entry %s', entry.options)


    mesh = AwoxMeshLight(hass, entry.data[CONF_MESH_NAME], entry.data[CONF_MESH_PASSWORD], entry.data[CONF_MESH_KEY])

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
