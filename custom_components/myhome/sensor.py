"""
Light mode sensor
"""
import logging
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup light mode sensors"""
    add_devices([LightModeSensor(hass)])


class LightModeSensor(Entity):
    """Representation of a light mode sensor."""
    def __init__(self, hass):
        self._name = 'test'
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""
        return {}

    def update(self):
        """Fetch new state data for the sensor."""
