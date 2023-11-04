"""Platform for light integration."""
from __future__ import annotations

import logging

from typing import Any

from .awox import AwoxMeshLight

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.light import SUPPORT_BRIGHTNESS

from homeassistant.components import bluetooth

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    LightEntity,
    ColorMode
)

from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICES,
    CONF_MAC,

    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from .const import DOMAIN, CONF_MESH_ID, CONF_MANUFACTURER, CONF_MODEL, CONF_FIRMWARE, CONF_MESH_NAME, CONF_MESH_PASSWORD


_LOGGER = logging.getLogger("awox")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.info('entry %s', entry.data)


    mesh = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.info('mesh %s', mesh)
    
    lights = []
    for device in entry.data[CONF_DEVICES]:
        # Skip non lights
        if 'light' not in device['type']:
            continue
        if CONF_MANUFACTURER not in device:
            device[CONF_MANUFACTURER] = None
        if CONF_MODEL not in device:
            device[CONF_MODEL] = None
        if CONF_FIRMWARE not in device:
            device[CONF_FIRMWARE] = None

        type_string = ''
        supported_color_modes = set()

        if 'type' in device:
            type_string = device['type']

        if 'color' in type_string:
            supported_color_modes.add(ColorMode.RGB)

        if 'temperature' in type_string:
            supported_color_modes.add(ColorMode.COLOR_TEMP)

        if 'dimming' in type_string:
            supported_color_modes.add(ColorMode.BRIGHTNESS)

        if len(supported_color_modes) == 0:
            supported_color_modes.add(ColorMode.ONOFF)
    
        #count = bluetooth.async_scanner_count(hass, connectable=True)
        #_LOGGER.info('count %s', count)

        mac = device[CONF_MAC].upper()
        _LOGGER.info('mac %s', mac)
        
        bledevice = bluetooth.async_ble_device_from_address(hass , mac , connectable=True)
        _LOGGER.info('ble_device %s', bledevice)
        

        light = AwoxLight(mesh, device[CONF_MAC], device[CONF_MESH_ID], device[CONF_NAME], supported_color_modes,
                          device[CONF_MANUFACTURER], device[CONF_MODEL], device[CONF_FIRMWARE], bledevice)
        
        _LOGGER.info(' :: Setup light [%d] %s', device[CONF_MESH_ID], device[CONF_NAME])

        lights.append(light)

    async_add_entities(lights)

class AwoxLight(LightEntity):
    """Representation of an Awox Light."""

    def __init__(self, coordinator: AwoxMeshLight, mac: str, mesh_id: int, name: str, supported_color_modes: set[str] | None,
                 manufacturer: str, model: str, firmware: str, ble_device):
        """Initialize an AwoX MESH Light."""
        self._mesh = coordinator
        self._mac = mac
        self._mesh_id = mesh_id
        self._ble = ble_device

        self._attr_name = name
        self._attr_unique_id = "awoxmesh-%s" % self._mesh_id
        self._attr_supported_color_modes = supported_color_modes

        self._manufacturer = manufacturer
        self._model = model
        self._firmware = firmware

        self._state = None
        self._color_mode = False
        self._red = None
        self._green = None
        self._blue = None
        self._white_temperature = None
        self._white_brightness = None
        self._color_brightness = None
        self._brightness = None

    
    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return bool(self._state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        status = {}
        """Instruct the light to turn on."""
        if self._ble is not None:
            _LOGGER.info("Turn on...%s", self._ble)
            resp = await AwoxMeshLight.connect_to_device(self._ble, b'\x01', self._mesh._mesh_name , self._mesh.mesh_password)
            _LOGGER.info("Turned on...%s ", resp)
            if resp is True:
                self._is_on = True
                status['state'] = True
                self._state = status['state'] 
                _LOGGER.info("Turned on...%s ", self._state)
        else:
            _LOGGER.info("No light detected")


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        status = {}

        if self._ble is not None:
            _LOGGER.info("Turn off...%s ", self._ble)
            resp = await AwoxMeshLight.connect_to_device(self._ble, b'\x00', self._mesh._mesh_name , self._mesh.mesh_password)
            _LOGGER.info("Turned off...%s ", resp)
            if resp is True:
                self._is_on = False
                status['state'] = False
                self._state = status['state']
                _LOGGER.info("Turned off...%s ", self._state)

        else:
            _LOGGER.info("No light detected")



