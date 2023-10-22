"""Awox device scanner class"""
import asyncio
import async_timeout
import logging

from homeassistant.core import HomeAssistant


from bleak import BleakClient, BleakScanner

_LOGGER = logging.getLogger("awox")

START_MAC_ADDRESS = "A4:C1"


class DeviceScanner:




    @staticmethod
    async def async_find_devices(hass: HomeAssistant, scan_timeout: int = 30):
        def init():
            _LOGGER.info('Initializing scanner...')
       
        devices = {}

        try:
            _LOGGER.info("Scanning %d seconds for AwoX bluetooth mesh devices!", scan_timeout)
            devices = await BleakScanner.discover(timeout=scan_timeout)
            
            _LOGGER.info('Found devices: %s', devices)
            selDevice = {}
            i = 0
            for device in devices:
                i = i + 1
                if device.address.startswith(START_MAC_ADDRESS): #== "A4:C1:38:77:2A:18":
                    selDevice.update({i: device})
                    _LOGGER.info("Found device: %s", selDevice)
                    
            _LOGGER.info("Found %s devices", len(selDevice))

        except Exception as e:
            _LOGGER.exception('Find devices process error: %s', e)

        return selDevice
