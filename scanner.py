"""Awox device scanner class"""
import asyncio
import async_timeout
import logging

from homeassistant.core import HomeAssistant


from bleak import BleakClient, BleakScanner

_LOGGER = logging.getLogger(__name__)

START_MAC_ADDRESS = "A4:C1"


class DeviceScanner:




    @staticmethod
    async def async_find_devices(hass: HomeAssistant, scan_timeout: int = 30):
        def init():
            _LOGGER.debug('Initializing scanner...')
       
        devices = {}

        try:
            bl = await hass.async_add_executor_job(init)
            _LOGGER.info("Scanning %d seconds for AwoX bluetooth mesh devices!", scan_timeout)
            await hass.async_add_executor_job(bl.start_scan)
            await asyncio.sleep(scan_timeout)

            for mac, dev in (await hass.async_add_executor_job(bl.get_available_devices)).items():
                if mac.startswith(START_MAC_ADDRESS):
                    devices[mac] = dev

            _LOGGER.debug('Found devices: %s', devices)

            await hass.async_add_executor_job(bl.stop_scan)

            async with async_timeout.timeout(10):
                await hass.async_add_executor_job(bl.shutdown)

        except Exception as e:
            _LOGGER.exception('Find devices process error: %s', e)

        return devices
