"""Platform for light integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from .awox import AwoxMeshLight
from .const import CONF_FIRMWARE, CONF_MANUFACTURER, CONF_MESH_ID, CONF_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _supported_color_modes(device_type: str) -> set[ColorMode]:
    """Return supported Home Assistant color modes for an AwoX device type."""
    modes: set[ColorMode] = set()

    if "color" in device_type:
        modes.add(ColorMode.RGB)

    if "temperature" in device_type:
        modes.add(ColorMode.COLOR_TEMP)

    # In Home Assistant, ColorMode.BRIGHTNESS must be the only supported mode
    # when used. RGB and COLOR_TEMP already include brightness support.
    if "dimming" in device_type and not modes:
        modes.add(ColorMode.BRIGHTNESS)

    if not modes:
        modes.add(ColorMode.ONOFF)

    return modes


def _default_color_mode(supported_color_modes: set[ColorMode]) -> ColorMode:
    """Return a valid initial color mode for the light."""
    for color_mode in (
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
        ColorMode.BRIGHTNESS,
        ColorMode.ONOFF,
    ):
        if color_mode in supported_color_modes:
            return color_mode

    return next(iter(supported_color_modes))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up AwoX lights from a config entry."""
    _LOGGER.info("entry %s", entry.data)

    mesh = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info("mesh %s", mesh)

    lights: list[AwoxLight] = []
    for device in entry.data[CONF_DEVICES]:
        device_type = device.get("type", "")

        # Skip non lights.
        if "light" not in device_type:
            continue

        supported_color_modes = _supported_color_modes(device_type)

        mac = device[CONF_MAC].upper()
        _LOGGER.info("mac %s", mac)

        ble_device = bluetooth.async_ble_device_from_address(
            hass, mac, connectable=True
        )
        _LOGGER.info("ble_device %s", ble_device)

        light = AwoxLight(
            mesh,
            device[CONF_MAC],
            device[CONF_MESH_ID],
            device[CONF_NAME],
            supported_color_modes,
            device.get(CONF_MANUFACTURER),
            device.get(CONF_MODEL),
            device.get(CONF_FIRMWARE),
            ble_device,
        )

        _LOGGER.info(" :: Setup light [%d] %s", device[CONF_MESH_ID], device[CONF_NAME])
        lights.append(light)

    async_add_entities(lights)


class AwoxLight(LightEntity):
    """Representation of an AwoX light."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: AwoxMeshLight,
        mac: str,
        mesh_id: int,
        name: str,
        supported_color_modes: set[ColorMode],
        manufacturer: str | None,
        model: str | None,
        firmware: str | None,
        ble_device,
    ) -> None:
        """Initialize an AwoX MESH light."""
        self._mesh = coordinator
        self._mac = mac
        self._mesh_id = mesh_id
        self._ble = ble_device

        self._attr_name = name
        self._attr_unique_id = f"awoxmesh-{mac.lower()}-{mesh_id}"
        self._attr_supported_color_modes = supported_color_modes
        self._attr_color_mode = _default_color_mode(supported_color_modes)

        if supported_color_modes != {ColorMode.ONOFF}:
            self._attr_brightness = 255

        self._manufacturer = manufacturer
        self._model = model
        self._firmware = firmware

        self._state: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if self._ble is None:
            _LOGGER.info("No light detected")
            return

        _LOGGER.info("Turn on...%s", self._ble)
        resp = await AwoxMeshLight.connect_to_device(
            self._ble,
            b"\x01",
            self._mesh._mesh_name,
            self._mesh.mesh_password,
        )
        _LOGGER.info("Turned on...%s ", resp)

        if resp is True:
            self._state = True
            if ATTR_BRIGHTNESS in kwargs:
                self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            self.async_write_ha_state()
            _LOGGER.info("Turned on...%s ", self._state)
            
    
    async def async_shutdown(self):
        """Clean shutdown for Home Assistant unload."""
        return        

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if self._ble is None:
            _LOGGER.info("No light detected")
            return

        _LOGGER.info("Turn off...%s ", self._ble)
        resp = await AwoxMeshLight.connect_to_device(
            self._ble,
            b"\x00",
            self._mesh._mesh_name,
            self._mesh.mesh_password,
        )
        _LOGGER.info("Turned off...%s ", resp)

        if resp is True:
            self._state = False
            self.async_write_ha_state()
            _LOGGER.info("Turned off...%s ", self._state)