import logging
import json
from functools import partial
from homeassistant.util import convert

CONF_EVENT_TYPE = "event_type"
CONF_EVENT_DATA = "event_data"

_LOGGER = logging.getLogger(__name__)

def handle_event(action, event_data, event):
    if event_data == event.data:
        action()

def register(hass, config, action):
    """ Listen for event changes based on config. """
    try:
        event_type = config.get(CONF_EVENT_TYPE)
    except:
        _LOGGER.error('Missing event_type')
        return False

    event_data = convert(config.get(CONF_EVENT_DATA), json.loads, {})
    hass.bus.listen(event_type, partial(handle_event, action, event_data))
    return True
