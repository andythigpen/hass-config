"""
custom_components.myhome
~~~~~~~~~~~~~~~~~~~~~~~~~

Custom rules/automation for my home
"""
import logging

from datetime import timedelta
from functools import partial

import homeassistant.components as core
import homeassistant.components.mysensors as mysensors
import homeassistant.helpers.event as helper
import homeassistant.util.dt as date_util

from homeassistant.components.device_tracker import (
    ATTR_DEV_ID, ATTR_LOCATION_NAME, SERVICE_SEE)
from homeassistant.components.device_tracker import (
    DOMAIN as DOMAIN_DEVICE_TRACKER)

from homeassistant.components.input_select import DOMAIN as DOMAIN_INPUT_SELECT
from homeassistant.components.input_select import SERVICE_SELECT_OPTION
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.mysensors import (ATTR_NODE_ID, ATTR_CHILD_ID)
from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE
from homeassistant.components.python_script import (
    DOMAIN as DOMAIN_PYTHON_SCRIPT)

from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE,
    SERVICE_TURN_OFF, SERVICE_TURN_ON,
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED, ATTR_HIDDEN)

from homeassistant.core import split_entity_id
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.service import (
    extract_entity_ids, call_from_config)

from homeassistant.util import (slugify, convert)

DOMAIN = 'myhome'
DOMAIN_ROOM = 'room'
ENTITY_ID = 'myhome.active'
DEPENDENCIES = ['group', 'scene', 'input_select', 'mysensors']

_LOGGER = logging.getLogger(__name__)

# room states
STATE_OCCUPIED = 'occupied'
STATE_NOT_OCCUPIED = 'not_occupied'
STATE_COUNTDOWN = 'countdown'

# default mode, does nothing
MODE_RESET = 'reset'

# configuration
CONF_ROOMS = 'rooms'
CONF_RFID = 'rfid'
CONF_TIMEOUT = 'timeout'
CONF_MODE = 'mode'
CONF_TOUCH = 'touch'
CONF_RESPONSE = 'response'

# services
SERVICE_DIM = 'dim'
SERVICE_BRIGHTEN = 'brighten'
SERVICE_SET_ROOM_OCCUPIED = 'set_room_occupied'
SERVICE_SET_AWAY = 'set_away'
SERVICE_ENABLE_SCENE = 'enable_scene'
SERVICE_SET_TOUCH = 'set_touch'

# attributes
ATTR_MODE = 'mode'
ATTR_BRIGHTNESS_STEP = 'brightness_step'
ATTR_COMMAND = 'command'


class MyHome(Entity):
    """
    Contains Room objects with sensors for tracking presence and performing
    actions based on location and "house mode".
    """
    def __init__(self, hass, mode_entity):
        self.hass = hass
        self.mode_entity = mode_entity
        self.entity_id = ENTITY_ID
        self.rooms = {}
        self._state = STATE_OFF
        self._register_services()

    @property
    def should_poll(self):
        """ Push state to HA instead of polling. """
        return False

    @property
    def name(self):
        """ Return the name based on the current state. """
        return 'Active' if self._state == STATE_ON else 'Not active'

    @property
    def icon(self):
        """ Set the icon based upon the current mode. """
        mode = self.mode
        if mode == 'morning':
            return 'mdi:weather-sunset-up'
        elif mode == 'day' or mode == 'afternoon':
            return 'mdi:weather-sunny'
        elif mode == 'evening':
            return 'mdi:weather-sunset-down'
        elif mode == 'night':
            return 'mdi:weather-night'
        elif mode == 'asleep':
            return 'mdi:sleep'
        return 'mdi:home-variant'

    @property
    def state(self):
        """ Returns the current house mode. """
        return self._state

    @state.setter
    def state(self, state):
        """ Sets automatic control of home on/off. """
        self._state = state
        self.schedule_update_ha_state()

    @property
    def mode(self):
        """ Get the current house mode via the configured entity. """
        mode = self.hass.states.get(self.mode_entity)
        if mode is None:
            return MODE_RESET
        return mode.state.lower()

    def _register_services(self):
        """ Adds service methods to HA. """
        self.hass.services.register(DOMAIN, SERVICE_SET_ROOM_OCCUPIED,
                                    self._set_room_occupied)
        self.hass.services.register(DOMAIN, SERVICE_SET_AWAY, self._set_away)
        self.hass.services.register(DOMAIN, SERVICE_ENABLE_SCENE,
                                    self._enable_scene_service)
        self.hass.services.register(DOMAIN, SERVICE_TURN_ON, self._turn_on)
        self.hass.services.register(DOMAIN, SERVICE_TURN_OFF, self._turn_off)

    def _set_room_occupied(self, service):
        """
        Service method to change a room mode to STATE_OCCUPIED.

        Sets all other rooms that were STATE_OCCUPIED to STATE_COUNTDOWN.
        """
        entity_id = service.data.get(ATTR_ENTITY_ID)
        _LOGGER.info('set room %s to occupied', entity_id)
        for room in self.rooms.values():
            if room.entity_id == entity_id:
                room.mode = STATE_OCCUPIED
                continue
            if room.mode != STATE_OCCUPIED:
                continue
            _LOGGER.info('starting timer for room %s', room)
            room.mode = STATE_COUNTDOWN

    def _set_away(self, service):
        """
        Sets all rooms to STATE_NOT_OCCUPIED when no one is home.
        """
        _LOGGER.info('setting all rooms to not occupied')
        for room in self.rooms.values():
            room.mode = STATE_NOT_OCCUPIED

    def _enable_scene_service(self, service):
        """ Service that turns on a scene based on room mode. """
        return self._enable_scene(service)

    def _enable_scene(self, service, room_mode=None):
        """
        Turns on a scene for a room with the given entity_id and the current
        house mode.
        """
        entity_id = service.data.get(ATTR_ENTITY_ID)
        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        room = self.get_room(entity_id)
        if room is None:
            _LOGGER.warning('Room %s not found, not enabling scene', entity_id)
            return
        if room.state != STATE_ON:
            _LOGGER.info('Room %s is in manual override mode', entity_id)
            return
        if room_mode is None:
            room_mode = room.mode
        entity_id = entity_id.replace('{}.'.format(DOMAIN_ROOM), '', 1)
        scene_name = '{}.{}_{}_{}'.format(DOMAIN_SCENE, entity_id,
                                          slugify(self.mode),
                                          slugify(room_mode))
        if scene_name not in self.hass.states.entity_ids(DOMAIN_SCENE):
            _LOGGER.warning('no scene configured with name %s', scene_name)
            return
        _LOGGER.info('turning on scene %s for room %s', scene_name, entity_id)
        self.hass.services.call(DOMAIN_SCENE, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: scene_name
        })

    def _turn_on(self, service):
        """ Service that enables myhome control. """
        self.state = STATE_ON

    def _turn_off(self, service):
        """ Service that disables myhome control. """
        self.state = STATE_OFF

    def add(self, room):
        """ Adds a room. """
        if room is not None:
            self.rooms[room.entity_id] = room

    def get_room(self, entity_id):
        """ Returns a room for corresponding entity id. """
        return self.rooms.get(entity_id, None)

    def __repr__(self):
        return '<home: %s>' % self.rooms


class Room(Entity):
    """
    Contains motion and light sensors and performs actions based on them,
    the current house mode, and a person's location in the house.
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self, hass, name, timeout):
        self._name = name
        self.entity_id = '{}.{}'.format(DOMAIN_ROOM, name)
        self.hass = hass
        self._state = STATE_ON
        self._mode = STATE_NOT_OCCUPIED
        self.timeout = timeout
        self.timer = None

    @property
    def should_poll(self):
        """ Push state to HA instead of polling. """
        return False

    @property
    def name(self):
        """ Returns the name of this room. """
        return self._name

    @property
    def icon(self):
        """ Sets the icon based upon the current mode. """
        if self._mode == STATE_OCCUPIED:
            return 'mdi:account'
        elif self._mode == STATE_NOT_OCCUPIED:
            return 'mdi:account-outline'
        elif self._mode == STATE_COUNTDOWN:
            return 'mdi:clock'
        return 'mdi:home-variant'

    @property
    def state(self):
        """ Returns the current room state (on/off). """
        return self._state

    @state.setter
    def state(self, state):
        """ Sets the current state of the room. """
        self._state = state
        self.schedule_update_ha_state()

    @property
    def mode(self):
        """ Returns the current room mode (occupied/not_occupied). """
        return self._mode

    @mode.setter
    def mode(self, mode):
        """ Sets the current room mode, triggering the timer as necessary. """
        self._mode = mode
        if self._mode == STATE_COUNTDOWN:
            self._start_timer()
        else:
            self._disable_timer()
        self.schedule_update_ha_state()

    @property
    def state_attributes(self):
        """ Returns the current room attributes. """
        return {
            'mode': self._mode,
            'timeout': str(self.timeout)
        }

    def _start_timer(self):
        """
        Registers a countdown timer that will trigger no occupancy when fired.
        Sets the state to STATE_COUNTDOWN.
        """
        if self.timer is not None:
            _LOGGER.info('timer already set: %s', self)
            return
        self.timer = helper.track_point_in_utc_time(self.hass,
            self._timer_expired, date_util.utcnow() + self.timeout)
        _LOGGER.info('set timer %s', self)

    def _disable_timer(self):
        """ Unregisters the timer, if set. """
        if self.timer is None:
            return
        _LOGGER.info('canceling timer %s', self)
        # call to remove event listener
        self.timer()
        self.timer = None

    def _timer_expired(self, now=None):
        """
        Event callback after countdown timer expires.

        Enable unoccupied scene, if configured for the current mode.
        """
        _LOGGER.info('timer expired %s', self)
        self.timer = None
        self.mode = STATE_NOT_OCCUPIED
        self.hass.services.call(DOMAIN_PYTHON_SCRIPT, 'enable_room_scene', {
            'room': self._name,
            'mode': self.mode,
        })

    def __repr__(self):
        return '<%s state:%s mode:%s timer:%s>' % (self.entity_id, self.state,
                                                   self.mode, self.timer)


def create_room(hass, name, conf):
    """ Returns a Room object given a configuration dict. """
    timeout = timedelta(**conf.get(CONF_TIMEOUT, {'minutes': 15}))
    return Room(hass, name, timeout)


def register_room_services(hass, myhome):
    """ Registers the services that handle rooms. """

    def update_room_state(state, service):
        """ Service that updates the room states. """
        entity_ids = extract_entity_ids(hass, service)
        for entity_id in entity_ids:
            room = myhome.get_room(entity_id)
            if room is None:
                _LOGGER.warning('Room %s not found', entity_id)
                return
            room.state = state

    hass.services.register(DOMAIN_ROOM, 'turn_on',
                           partial(update_room_state, STATE_ON))
    hass.services.register(DOMAIN_ROOM, 'turn_off',
                           partial(update_room_state, STATE_OFF))


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
            ATTR_DEV_ID: split_entity_id(rfid_sensor)[1],
            ATTR_LOCATION_NAME: location,
        })

    helper.track_utc_time_change(hass, rfid_seen, second=0)

    def rfid_state_change(entity_id, old_state, new_state):
        """ Calls see service immediately with state of RFID sensor. """
        rfid_seen()

    helper.track_state_change(hass, rfid_sensor, rfid_state_change)


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
    if bri <= 0:
        core.turn_off(hass, target_ids)
    elif bri <= 255:
        core.turn_on(hass, target_ids, brightness=bri)


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
        for gateway in gateways:
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
        helper.track_state_change(hass, controller, controller_state_change)


def setup(hass, config):
    """ Setup myhome component. """
    mode_entity = config[DOMAIN].get(CONF_MODE, None)

    if mode_entity is None:
        _LOGGER.error('Missing mode entity configuration')
        return

    home = MyHome(hass, mode_entity)
    room_conf = config[DOMAIN].get(CONF_ROOMS, {})
    for name, conf in room_conf.items():
        room = create_room(hass, name, conf)
        room.schedule_update_ha_state()
        home.add(room)

    register_room_services(hass, home)

    home.schedule_update_ha_state()
    _LOGGER.info('myhome loaded: %s', home)

    register_presence_handlers(hass, config)
    _LOGGER.info('registered presense handlers')

    register_touch_control_handlers(hass, config)
    _LOGGER.info('registered touch control handlers')

    return True
