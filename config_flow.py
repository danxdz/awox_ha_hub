import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD
)


from .const import DOMAIN, CONF_MESH_NAME, CONF_MESH_PASSWORD, CONF_MESH_KEY



_LOGGER = logging.getLogger(__name__)

class AwoxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_awox_connect(self, user_input: Optional[Mapping] = None):

        errors = {}
        username: str = ''
        password: str = ''
        awox_connect = None

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

        if user_input is None or awox_connect is None or errors:
            return self.async_show_form(
                step_id="awox_connect",
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME, default=username): str,
                    vol.Required(CONF_PASSWORD, default=password): str,
                }),
                errors=errors,
            )
