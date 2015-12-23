"""
custom_components.myhome
~~~~~~~~~~~~~~~~~~~~~~~~~

Custom rules/automation for my home
"""
import logging

from datetime import timedelta
from functools import partial

import homeassistant.util.dt as date_util
import homeassistant.helpers.event as helper
from homeassistant.util import slugify
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_NOT_HOME, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED)


DOMAIN = 'myhome'
ENTITY_ID = 'myhome.active'
DEPENDENCIES = ['group', 'sun']

_LOGGER = logging.getLogger(__name__)


STATE_OCCUPIED = 'occupied'
STATE_NOT_OCCUPIED = 'not_occupied'
STATE_COUNTDOWN = 'countdown'

# default state, does nothing
STATE_RESET = 'reset'

CONF_ROOMS = 'rooms'
CONF_LIGHT = 'light'
CONF_MOTION = 'motion'
CONF_TIMEOUT = 'timeout'
CONF_MODES = 'modes'
CONF_OCCUPIED = 'occupied'
CONF_NOT_OCCUPIED = 'not_occupied'
CONF_THRESHOLD = 'threshold'
CONF_LOW = 'low'
CONF_HIGH = 'high'

ATTR_TRANSITION = 'transition'
ATTR_MODE = 'mode'

DOMAIN_ROOM = 'room'
DOMAIN_LIGHT = 'light'
DOMAIN_SCENE = 'scene'


class MyHome(Entity):
    """
    Contains Room objects with sensors for tracking presence and performing
    actions based on location and "house mode".
    """
    def __init__(self, hass):
        self.hass = hass
        self.entity_id = ENTITY_ID
        self.rooms = {}
        self._state = STATE_OFF
        self._register_services()
        self._mode = STATE_RESET

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return 'Active'

    @property
    def state(self):
        """ Returns the current house mode. """
        return self._state

    @state.setter
    def state(self, state):
        """ Sets automatic control of home on/off. """
        self._state = state
        self.update_ha_state()

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode):
        self._mode = mode
        self.update_ha_state()

    @property
    def state_attributes(self):
        return {
            'mode': self._mode
        }

    def _register_services(self):
        """ Adds service methods to HA. """
        self.hass.services.register(DOMAIN, 'set_mode', self._set_mode_service)
        self.hass.services.register(DOMAIN, 'set_occupied', self._set_occupied)
        self.hass.services.register(DOMAIN, 'set_away', self._set_away)
        self.hass.services.register(DOMAIN, 'set_scene', self._set_scene)
        self.hass.services.register(DOMAIN, 'turn_on', self._turn_on)
        self.hass.services.register(DOMAIN, 'turn_off', self._turn_off)

    def _set_mode_service(self, service):
        """ Service method for setting mode. """
        self.mode = service.data.get(ATTR_MODE)

    def _set_occupied(self, service):
        """
        Service method to change a room state to STATE_OCCUPIED.

        Sets all other rooms that were STATE_OCCUPIED to STATE_COUNTDOWN.
        """
        entity_id = service.data.get(ATTR_ENTITY_ID)
        _LOGGER.info('set room %s to occupied', entity_id)
        for room in self.rooms.values():
            if room.entity_id == entity_id:
                room.state = STATE_OCCUPIED
                continue
            if room.state != STATE_OCCUPIED:
                continue
            _LOGGER.info('starting timer for room %s', room)
            room.state = STATE_COUNTDOWN

    def _set_away(self, service):
        """
        Sets all rooms to STATE_NOT_OCCUPIED when no one is home.
        """
        _LOGGER.info('setting all rooms to not occupied')
        for room in self.rooms.values():
            room.state = STATE_NOT_OCCUPIED

    def _set_scene(self, service):
        """
        Turns on a scene for a room with the given entity_id and the current
        house mode.
        """
        entity_id = service.data.get(ATTR_ENTITY_ID)
        if entity_id.startswith(DOMAIN_ROOM):
            entity_id = entity_id.replace('{}.'.format(DOMAIN_ROOM), '', 1)
        scene_name = '{}.{}_{}'.format(DOMAIN_SCENE, entity_id,
                                       slugify(self.mode))
        if scene_name not in self.hass.states.entity_ids(DOMAIN_SCENE):
            _LOGGER.warning('no scene configured with name %s', scene_name)
            return
        _LOGGER.info('turning on scene %s for room %s', scene_name, entity_id)
        self.hass.services.call(DOMAIN_SCENE, SERVICE_TURN_ON, {
            'entity_id': scene_name
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

    def __repr__(self):
        return '<home: %s>' % self.rooms


class Room(Entity):
    """
    Contains motion and light sensors and performs actions based on them,
    the current house mode, and a person's location in the house.
    """
    def __init__(self, hass, name, motion, light, timeout, modes):
        self._name = name
        self.entity_id = '{}.{}'.format(DOMAIN_ROOM, name)
        self.hass = hass
        self._state = STATE_NOT_OCCUPIED
        self.motion = motion
        self.light = light
        self.timeout = timeout
        self.timer = None
        self.modes = modes

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Returns the current room state (occupied/not_occupied). """
        return self._state

    @state.setter
    def state(self, new_state):
        self._state = new_state
        if self._state == STATE_COUNTDOWN:
            self.start_timer()
        else:
            self.disable_timer()
        self.update_ha_state()

    def start_timer(self):
        """
        Registers a countdown timer that will trigger no occupancy when fired.
        Sets the state to STATE_COUNTDOWN.
        """
        if self.timer is not None:
            _LOGGER.info('start_timer: timer already set: %s', self)
            return
        self.timer = helper.track_point_in_utc_time(self.hass,
            self.not_occupied, date_util.utcnow() + self.timeout)
        _LOGGER.info('start_timer: set timer %s', self)

    def disable_timer(self):
        """ Unregisters the timer, if set. """
        if self.timer is None:
            return
        _LOGGER.info('canceling timer %s', self)
        self.hass.bus.remove_listener(EVENT_TIME_CHANGED, self.timer)
        self.timer = None

    def get_mode_config(self):
        """
        Returns the config for the current mode, or None if the current mode
        has no config.
        """
        home_mode = self.hass.states.get(ENTITY_ID).state_attributes['mode']
        mode = self.modes.get(home_mode.state)
        _LOGGER.info('modes: %s, entity: %s, mode: %s',
                     self.modes, home_mode, mode)
        return mode

    def get_light_data(self, mode, key):
        """
        Returns data from a mode config dict that can be passed to a light
        service call.   If entity_id is not present, it will be added.
        """
        if mode is None:
            return None
        conf = mode[key] or {}
        if ATTR_ENTITY_ID not in conf:
            conf[ATTR_ENTITY_ID] = 'group.{}'.format(self._name)
        return conf

    def not_occupied(self, now=None):
        """
        Event callback after countdown timer expires.

        Turns off the lights, if configured for the current mode.
        """
        _LOGGER.info('not_occupied %s', self)
        self.hass.states.set(self.entity_id, STATE_NOT_OCCUPIED)
        mode = self.get_mode_config()
        data_off = self.get_light_data(mode, CONF_NOT_OCCUPIED)
        if data_off:
            _LOGGER.info('not_occupied: turning off: %s', data_off)
            self.hass.services.call(DOMAIN_LIGHT, SERVICE_TURN_OFF, data_off)
        else:
            _LOGGER.info('not_occupied: no configuration for current mode')

    def __repr__(self):
        return '<%s state:%s timer:%s>' % (self.entity_id, self.state,
                                           self.timer)


def create_room(hass, name, conf):
    """ Returns a Room object given a configuration dict. """
    if not conf.get(CONF_MOTION):
        _LOGGER.warning('No motion sensors defined for room %s', name)
        return
    motion = conf[CONF_MOTION]
    light = conf.get(CONF_LIGHT, {})
    timeout = timedelta(**conf.get(CONF_TIMEOUT, {'minutes': 15}))
    modes = conf.get(CONF_MODES, {})
    return Room(hass, name, motion, light, timeout, modes)


def setup(hass, config):
    """ Setup myhome component. """

    home = MyHome(hass)
    room_conf = config[DOMAIN].get(CONF_ROOMS, {})
    for name, conf in room_conf.items():
        room = create_room(hass, name, conf)
        room.update_ha_state()
        home.add(room)

    home.update_ha_state()
    _LOGGER.info('myhome loaded: %s', home)

    return True
