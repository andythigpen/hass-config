"""
custom_components.lighthub
~~~~~~~~~~~~~~~~~~~~~~~~~

Interfaces with light switch hub via lighthub module
"""
import logging
from functools import partial
from lighthub import LightSwitchHub, Command, Gesture, Electrode
from cmdmessenger import CmdMessengerHandler

from homeassistant.helpers import validate_config, extract_entity_ids
import homeassistant.components as core
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.util import convert
from homeassistant.loader import get_component

DOMAIN = 'lighthub'

# List of component names (string) your component depends upon
# We depend on group because group will be loaded after all the components that
# initalize devices have been setup.
DEPENDENCIES = ['group']

CONF_PORT = 'port'
CONF_BAUD = 'baud'
CONF_TIMEOUT = 'timeout'

# Name of the service that we expose
SERVICE_TOGGLE = 'toggle'
SERVICE_DIM = 'dim'
SERVICE_BRIGHTEN = 'brighten'

EVENT_LIGHTHUB_CHANGED = 'lighthub_changed'
EVENT_LIGHTHUB_STATUS = 'lighthub_status'

ATTR_BRIGHTNESS_STEP = 'brightness_step'

_LOGGER = logging.getLogger(__name__)

class Handler(CmdMessengerHandler):
    def __init__(self, eventbus):
        super(CmdMessengerHandler, self).__init__()
        self.eventbus = eventbus

    @CmdMessengerHandler.handler(Command.msg)
    def handle_debug(self, msg):
        _LOGGER.info(msg.read_str())

    @CmdMessengerHandler.handler(Command.touch_event)
    def handle_touch_event(self, msg):
        nodeid = msg.read_int8()
        gesture = msg.read_int8()
        electrode = msg.read_int8()
        repeat = msg.read_int8()
        _LOGGER.info('[{}] gesture: {}, electrode: {}, repeat: {}'.format(
            nodeid, gesture, electrode, repeat))
        self.eventbus.fire(EVENT_LIGHTHUB_CHANGED, {
            'nodeid'    : nodeid,
            'gesture'   : gesture,
            'electrode' : electrode,
            'repeat'    : repeat,
        })

    @CmdMessengerHandler.handler(Command.status_event)
    def handle_status_event(self, msg):
        #TODO: display a warning if vcc is too low
        nodeid = msg.read_int8()
        vcc = msg.read_int32()
        count = msg.read_int16()
        _LOGGER.info("[{}] status: vcc {}, count {}".format(nodeid, vcc, count))
        self.eventbus.fire(EVENT_LIGHTHUB_STATUS, {
            'nodeid': nodeid,
            'vcc'   : vcc,
            'count' : count,
        })


def handle_light_toggle(hass, service):
    target_ids = service.data[ATTR_ENTITY_ID]
    for target_id in target_ids:
        if core.is_on(hass, target_id):
            core.turn_off(hass, target_id)
        else:
            core.turn_on(hass, target_id)

def get_brightness(hass, service):
    # there's no brightness attribute for a group so just pick the first one
    # in the group and return that
    group = get_component('group')
    target_ids = group.expand_entity_ids(hass, service.data[ATTR_ENTITY_ID])
    target_id = target_ids[0]
    state = hass.states.get(target_id)
    return state.attributes.get(ATTR_BRIGHTNESS, 0)

def change_brightness(hass, service, bri):
    for target_id in service.data[ATTR_ENTITY_ID]:
        if bri <= 0:
            core.turn_off(hass, target_id)
        elif bri <= 255:
            core.turn_on(hass, target_id, brightness=bri)

def handle_light_dim(hass, service):
    bri = get_brightness(hass, service)
    bri -= convert(service.data.get(ATTR_BRIGHTNESS_STEP), int, 50)
    change_brightness(hass, service, bri)

def handle_light_brighten(hass, service):
    bri = get_brightness(hass, service)
    bri += convert(service.data.get(ATTR_BRIGHTNESS_STEP), int, 50)
    change_brightness(hass, service, bri)

def setup(hass, config):
    """Setup lighthub component. """

    # Validate that all required config options are given
    required = {
        DOMAIN: [CONF_PORT]
    }

    if not validate_config(config, required, _LOGGER):
        return False

    try:
        port = config[DOMAIN][CONF_PORT]
        baud = int(config[DOMAIN].get(CONF_BAUD, 115200))
        timeout = float(config[DOMAIN].get(CONF_TIMEOUT, 1.0))
    except:
        _LOGGER.exception('Invalid parameter(s)')
        return False

    hub = LightSwitchHub(handlers=Handler(hass.bus))
    try:
        hub.connect(port, baud, timeout)
    except Exception as e:
        _LOGGER.exception('Error connecting to hub')
        return False

    hass.services.register(DOMAIN, SERVICE_TOGGLE,
            partial(handle_light_toggle, hass))
    hass.services.register(DOMAIN, SERVICE_DIM,
            partial(handle_light_dim, hass))
    hass.services.register(DOMAIN, SERVICE_BRIGHTEN,
            partial(handle_light_brighten, hass))

    return True
