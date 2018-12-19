"""
custom_components.myhome
~~~~~~~~~~~~~~~~~~~~~~~~~

Custom rules/automation for my home
"""
import datetime
import itertools
import logging
import time

from collections import namedtuple
from functools import partial

import homeassistant.components.mysensors as mysensors

from homeassistant.components.device_tracker import (
    ATTR_DEV_ID, ATTR_LOCATION_NAME, SERVICE_SEE)
from homeassistant.components.device_tracker import (
    DOMAIN as DOMAIN_DEVICE_TRACKER)

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.mysensors.device import (
    ATTR_NODE_ID, ATTR_CHILD_ID)
from homeassistant.components.scene.homeassistant import (
    _process_config, HomeAssistantScene)

from homeassistant.const import (
    STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE,
    SERVICE_TURN_ON, SERVICE_TURN_OFF,
    ATTR_ENTITY_ID,
    CONF_NAME, CONF_ENTITIES,
)

from homeassistant import core
from homeassistant.helpers import event
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    extract_entity_ids, call_from_config)
from homeassistant.helpers.state import async_reproduce_state

from homeassistant.util import convert
from homeassistant.util import dt as dt_util


DOMAIN = 'myhome'

DEPENDENCIES = ['group', 'scene', 'input_select', 'mysensors']

_LOGGER = logging.getLogger(__name__)

# configuration
CONF_RFID = 'rfid'
CONF_TOUCH = 'touch'
CONF_RESPONSE = 'response'
CONF_ROOMS = 'rooms'
CONF_MODES= 'modes'

# services
SERVICE_DIM = 'dim'
SERVICE_BRIGHTEN = 'brighten'
SERVICE_SET_TOUCH = 'set_touch'
SERVICE_SEND_MSG = 'send_msg'

# attributes
ATTR_BRIGHTNESS_STEP = 'brightness_step'
ATTR_COMMAND = 'command'
ATTR_VALUE_TYPE = 'value_type'
ATTR_SUB_TYPE = 'sub_type'
ATTR_ACK = 'ack'
ATTR_PAYLOAD = 'payload'


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def service_send_message(hass, service):
    """Send an arbitrary message to a MySensors node"""
    from mysensors.mysensors import Message
    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if gateways is None:
        _LOGGER.warning("MySensors gateways config is unavailable")
        return
    entity_ids = extract_entity_ids(hass, service)
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        attr = state.attributes
        node_id = attr.get(ATTR_NODE_ID, 0)
        child_id = attr.get(ATTR_CHILD_ID, 0)
        value_type = service.data.get(ATTR_VALUE_TYPE, 0)
        sub_type = service.data.get(ATTR_SUB_TYPE, 0)
        ack = service.data.get(ATTR_ACK, 0)
        payload = service.data.get(ATTR_PAYLOAD, '')
        for _, gateway in gateways.items():
            msg = Message().modify(
                node_id=node_id,
                child_id=child_id,
                type=value_type,
                sub_type=sub_type,
                ack=ack,
                payload=payload,
            )
            gateway.add_job(msg.encode)


def register_presence_handlers(hass, config):
    """ Registers the event handlers that handle presence. """
    rfid_sensor = config[DOMAIN].get(CONF_RFID, None)
    if rfid_sensor is None:
        _LOGGER.warning('RFID sensor not configured.')
        return

    def rfid_seen(now=None):
        """ Calls see service periodically with state of RFID sensor. """
        rfid_state = hass.states.get(rfid_sensor)
        location = STATE_NOT_HOME
        if rfid_state is not None and str(rfid_state.state) == '1':
            location = STATE_HOME
        # _LOGGER.debug('rfid %s state is %s', rfid_sensor, location)
        hass.services.call(DOMAIN_DEVICE_TRACKER, SERVICE_SEE, {
            ATTR_DEV_ID: core.split_entity_id(rfid_sensor)[1],
            ATTR_LOCATION_NAME: location,
        })

    event.track_utc_time_change(hass, rfid_seen, second=0)

    def rfid_state_change(entity_id, old_state, new_state):
        """ Calls see service immediately with state of RFID sensor. """
        rfid_seen()

    event.track_state_change(hass, rfid_sensor, rfid_state_change)


def get_brightness(hass, service):
    """ Returns the brightness for a group. """
    # there's no brightness attribute for a group so just pick the first one
    # in the group and return that
    target_ids = extract_entity_ids(hass, service)
    target_id = target_ids[0]
    state = hass.states.get(target_id)
    return state.attributes.get(ATTR_BRIGHTNESS, 0)


def change_brightness(hass, service, bri):
    """ Actually brightens/dims a group. """
    target_ids = extract_entity_ids(hass, service)
    service_data = {
        ATTR_ENTITY_ID: target_ids,
    }
    if bri <= 0:
        hass.services.call(core.DOMAIN, SERVICE_TURN_OFF, service_data)
    elif bri <= 255:
        service_data['brightness'] = bri
        hass.services.call(core.DOMAIN, SERVICE_TURN_ON, service_data)


def service_light_dim(hass, service):
    """ Dims lights by a step value. """
    bri = get_brightness(hass, service)
    bri -= convert(service.data.get(ATTR_BRIGHTNESS_STEP), int, 50)
    bri = max(0, bri)
    change_brightness(hass, service, bri)


def service_light_brighten(hass, service):
    """ Brightens lights by a step value. """
    bri = get_brightness(hass, service)
    bri += convert(service.data.get(ATTR_BRIGHTNESS_STEP), int, 50)
    bri = min(255, bri)
    change_brightness(hass, service, bri)


def register_touch_control_handlers(hass, config):
    """ Registers handlers for touch scene controllers. """
    hass.services.register(DOMAIN, SERVICE_DIM,
            partial(service_light_dim, hass))
    hass.services.register(DOMAIN, SERVICE_BRIGHTEN,
            partial(service_light_brighten, hass))

    controllers = config[DOMAIN].get(CONF_TOUCH, None)
    if controllers is None:
        _LOGGER.info('No touch controllers configured.')
        return

    def send_scene_response(node_id, child_id, value):
        """ Sends a response to a sensor. """
        gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
        if gateways is None:
            _LOGGER.warning("MySensors gateways config is unavailable")
            return
        for _, gateway in gateways.items():
            value_type = gateway.const.SetReq.V_SCENE_ON
            gateway.set_child_value(node_id, child_id, value_type, value)

    def set_touch_service(service):
        """ Service that sends a command to a touch controller. """
        entity_ids = extract_entity_ids(hass, service)
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            attr = state.attributes
            node_id = attr.get(ATTR_NODE_ID, None)
            child_id = attr.get(ATTR_CHILD_ID, None)
            cmd = service.data.get(ATTR_COMMAND, 0)
            send_scene_response(node_id, child_id, cmd)

    hass.services.register(DOMAIN, SERVICE_SET_TOUCH, set_touch_service)

    def controller_state_change(entity_id, old_state, new_state):
        """ Callback for touch controller state change. """
        if new_state.state == STATE_UNAVAILABLE:
            return
        try:
            state = int(new_state.state)
        except ValueError:
            _LOGGER.error("Invalid state %s", new_state.state)
            return
        attr = new_state.attributes
        controller = controllers[entity_id]
        action = controller.get(state, None)
        if action is not None:
            # remove response before call or config will not validate
            response = action.pop(CONF_RESPONSE, int(state))
            call_from_config(hass, action)
            if response is not None:
                node_id = attr.get(ATTR_NODE_ID, None)
                child_id = attr.get(ATTR_CHILD_ID, None)
                _LOGGER.debug("Sending response %s to %s.%s",
                              response, node_id, child_id)
                send_scene_response(node_id, child_id, response)
        elif state != 0:
            _LOGGER.warning('Action not found for state %s', state)
        # reset the touch controller state
        hass.states.set(entity_id, 0, attr)

    for controller in controllers:
        event.track_state_change(hass, controller, controller_state_change)


def monkeypatch_serial_gateway(hass):
    """
    Monkey patch the send method to rate limit writes since
    my gateway fails even at low baud rates.
    """
    from mysensors.mysensors import SerialGateway
    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if gateways is None:
        _LOGGER.warning("MySensors gateways config is unavailable")
        return
    for _, gateway in gateways.items():
        if not isinstance(gateway, SerialGateway):
            continue
        _LOGGER.info("monkeypatching MySensors serial gateway")
        send = gateway.send
        def send_delay(*args, **kwargs):
            ret = send(*args, **kwargs)
            time.sleep(0.095)
            return ret
        gateway.send = send_delay


#RoomMode = namedtuple('RoomMode', ['start', 'end', 'duration'])
class RoomMode:
    def __init__(self, name, start, end):
        self.name = name
        self.start = start
        self.end = end

    @property
    def duration(self):
        if self.end is None:
            return 0
        st = datetime.datetime.combine(dt_util.now(), self.start)
        en = datetime.datetime.combine(dt_util.now(), self.end)
        return (en - st).total_seconds()

    def __repr__(self):
        return "<{} name={} start={} end={}>".format(
            self.__class__.__name__, self.name, self.start, self.end)


class Easing:
    """
    Easing functions from https://easings.net/ and http://robertpenner.com/easing/
    t: current time
    b: beginning value
    c: change in value
    d: duration
    """
    @staticmethod
    def in_out_quad(t, b, c, d):
        t = t / d * 2
        if t < 1:
            return int(round(c / 2 * t * t + b))
        return int(round(-c / 2 * ((t - 1) * (t - 3) - 1) + b))

    @staticmethod
    def in_quad(t, b, c, d):
        t = t / d
        return int(round(c * (t ** 2) + b))

    @staticmethod
    def out_quad(t, b, c, d):
        t = t / d
        return int(round(-c * t * (t - 2) + b))


def get_transition_state(current_state, next_state, easing_method, current_time, duration):
    easing = getattr(Easing, easing_method)
    attributes = current_state.attributes.copy()
    for name, value in current_state.attributes.items():
        if name not in next_state.attributes:
            continue
        next_value = next_state.attributes[name]
        if name == 'rgb_color':
            attributes[name] = [
                easing(current_time, c, next_value[i] - c, duration)
                for i, c in enumerate(value)
            ]
        else:
            attributes[name] = easing(current_time, value, next_value - value, duration)
    return core.State(current_state.entity_id, current_state.state, attributes)


class RoomScene(HomeAssistantScene):
    """A scene is a group of entities and the states we want them to be."""

    def __init__(self, hass, room_id, mode_name, scene_config):
        """Initialize the scene."""
        super().__init__(hass, scene_config)
        self.room_id = room_id
        self.mode_name = mode_name
        self.easing_method = 'in_out_quad'

    def __repr__(self):
        return "<{} room={} mode={}>".format(
            self.__class__.__name__, self.room_id, self.mode_name)

    @property
    def states(self):
        return self.scene_config.states

    def get_values(self, now=None):
        _LOGGER.info('interpolating values for %s', now)
        if now is None:
            now = dt_util.now()
            start = datetime.datetime.combine(now, self.mode.start)
            now = (now - start).total_seconds()
            _LOGGER.info('setting now to %s', now)
        mode, next_mode = get_mode_and_next(self.hass, self.mode_name)
        states = self.states
        _LOGGER.info('mode, next_mode = %s, %s', mode, next_mode)
        _LOGGER.info('duration = %s', mode.duration)
        if mode is None or next_mode is None:
            return states.values()
        domain = self.hass.data[DOMAIN]
        room = domain[CONF_ROOMS][self.room_id]
        next_states = room[next_mode.name].states
        transition_states = []
        for entity, state in states.items():
            _LOGGER.info('entity %s, state %s', entity, state)
            if entity not in next_states:
                _LOGGER.info('entity %s not in next state', entity)
                transition_states.append(state)
                continue
            next_state = next_states[entity]
            transition_states.append(
                get_transition_state(state, next_state, self.easing_method, now, mode.duration)
            )
            _LOGGER.info('entity %s transition state %s', entity, transition_states[-1])
        return transition_states

    async def async_activate(self, now=None):
        """Activate scene. Try to get entities into requested state."""
        values = self.get_values(now)
        _LOGGER.info('scene states %s', values)
        await async_reproduce_state(self.hass, values, True)


def get_mode_and_next(hass, name):
    """Returns the mode with the given name and the next mode"""
    domain = hass.data[DOMAIN]
    modes = domain[CONF_MODES]
    for mode, next_mode in pairwise(modes):
        if mode.name == name:
            return mode, next_mode
    if modes[-1].name == name:
        return modes[-1], None
    return None, None


def add_room_modes(hass, config):
    domain = hass.data[DOMAIN]
    modes = config[DOMAIN].get(CONF_MODES)

    domain[CONF_MODES] = []
    for mode, next_mode in pairwise(modes):
        name = mode['name']
        start = dt_util.parse_time(mode['start'])
        end = dt_util.parse_time(next_mode['start'])
        domain[CONF_MODES].append(RoomMode(name, start, end))

    last_mode = modes[-1]
    name = last_mode['name']
    start = dt_util.parse_time(last_mode['start'])
    domain[CONF_MODES].append(RoomMode(name, start, None))


def add_scene_entities(hass, config):
    """Adds scene entities for each configured room/mode"""
    component = hass.data['scene']
    domain = hass.data[DOMAIN]
    domain[CONF_ROOMS] = {}
    rooms = domain[CONF_ROOMS]
    scenes = []
    for room_id, modes in config[DOMAIN].get(CONF_ROOMS).items():
        if room_id not in rooms:
            rooms[room_id] = {}
        for mode_name, entities in modes.items():
            scene_config = {
                CONF_NAME: 'Room {} {}'.format(room_id, mode_name),
                CONF_ENTITIES: entities,
            }
            scene = RoomScene(
                hass, room_id, mode_name, _process_config(scene_config))
            rooms[room_id][mode_name] = scene
            scenes.append(scene)
    if scenes:
        component.add_entities(scenes)
    return True


#import tracemalloc
#tracemalloc.start()
#prev_snapshot = tracemalloc.take_snapshot()

def setup(hass, config):
    """Setup myhome component."""
    hass.data[DOMAIN] = {}

    register_presence_handlers(hass, config)
    _LOGGER.info('registered presense handlers')

    hass.services.register(DOMAIN, SERVICE_SEND_MSG,
        partial(service_send_message, hass))
    monkeypatch_serial_gateway(hass)
    _LOGGER.info('monkey patched mysensors')

    register_touch_control_handlers(hass, config)
    _LOGGER.info('registered touch control handlers')

    add_room_modes(hass, config)
    _LOGGER.info('added room modes')
    add_scene_entities(hass, config)
    _LOGGER.info('added scene entities')

    async def test_scene_transition(service):
        _LOGGER.info('scene transition start')
        now = service.data.get('now', None)
        mode = service.data.get('mode', None)
        room = service.data.get('room', None)
        scene = hass.data[DOMAIN][CONF_ROOMS][room][mode]
        _LOGGER.info('using %s %s %s %s', now, mode, room, scene)
        await scene.async_activate(now)
        _LOGGER.info('scene transition end')

    hass.services.register(DOMAIN, 'test', test_scene_transition)

    # memory leak helper
    #def collect_stats(service):
    #    """Service that collects memory stats to track down a leak."""
    #    global prev_snapshot
    #    cur_snapshot = tracemalloc.take_snapshot()
    #    top_stats = cur_snapshot.compare_to(prev_snapshot, 'lineno')
    #    _LOGGER.info("MEMORY [Top 10]")
    #    for stat in top_stats[:10]:
    #        _LOGGER.info(stat)
    #    #prev_snapshot = cur_snapshot
    #hass.services.register(DOMAIN, 'collect_stats', collect_stats)
    # end memory leak helper

    return True
