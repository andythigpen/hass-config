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
from homeassistant.helpers.entity import (Entity, split_entity_id)
from homeassistant.helpers.service import extract_entity_ids
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_HOME, STATE_NOT_HOME,
    SERVICE_TURN_OFF, SERVICE_TURN_ON,
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED, ATTR_HIDDEN)
from homeassistant.components.device_tracker import (
    ATTR_DEV_ID, ATTR_LOCATION_NAME, SERVICE_SEE)
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN


DOMAIN = 'myhome'
ENTITY_ID = 'myhome.active'
DEPENDENCIES = ['group', 'scene']

_LOGGER = logging.getLogger(__name__)


STATE_OCCUPIED = 'occupied'
STATE_NOT_OCCUPIED = 'not_occupied'
STATE_COUNTDOWN = 'countdown'

# default state, does nothing
STATE_RESET = 'reset'

CONF_ROOMS = 'rooms'
CONF_RFID = 'rfid'
CONF_TIMEOUT = 'timeout'

ATTR_MODE = 'mode'

DOMAIN_ROOM = 'room'
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
        self._mode = STATE_RESET
        self._register_services()

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        """ Set the name based on the current mode. """
        return self._mode.title()

    @property
    def icon(self):
        """ Set the icon based upon the current mode. """
        mode = self._mode.lower()
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
        self.hass.services.register(DOMAIN, 'set_room_occupied',
                                    self._set_room_occupied)
        self.hass.services.register(DOMAIN, 'set_away', self._set_away)
        self.hass.services.register(DOMAIN, 'enable_occupied_scene',
                                    self._enable_occupied_scene)
        self.hass.services.register(DOMAIN, 'enable_unoccupied_scene',
                                    self._enable_unoccupied_scene)
        self.hass.services.register(DOMAIN, 'turn_on', self._turn_on)
        self.hass.services.register(DOMAIN, 'turn_off', self._turn_off)

    def _set_mode_service(self, service):
        """ Service method for setting mode. """
        self.mode = service.data.get(ATTR_MODE)

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

    def _enable_occupied_scene(self, service):
        return self._enable_scene(service, STATE_OCCUPIED)

    def _enable_unoccupied_scene(self, service):
        return self._enable_scene(service, STATE_NOT_OCCUPIED)

    def _enable_scene(self, service, room_mode):
        """
        Turns on a scene for a room with the given entity_id and the current
        house mode.
        """
        entity_id = service.data.get(ATTR_ENTITY_ID)
        room = self.get_room(entity_id)
        if room is None:
            _LOGGER.warning('Room %s not found, not enabling scene', entity_id)
            return
        if room.state != STATE_ON:
            _LOGGER.info('Room %s is in manual override mode', entity_id)
            return
        entity_id = entity_id.replace('{}.'.format(DOMAIN_ROOM), '', 1)
        scene_name = '{}.{}_{}_{}'.format(DOMAIN_SCENE, entity_id,
                                          slugify(self.mode),
                                          slugify(room_mode))
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
        return False

    @property
    def name(self):
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
        self._state = state
        self.update_ha_state()

    @property
    def mode(self):
        """ Returns the current room mode (occupied/not_occupied). """
        return self._mode

    @mode.setter
    def mode(self, mode):
        self._mode = mode
        if self._mode == STATE_COUNTDOWN:
            self._start_timer()
        else:
            self._disable_timer()
        self.update_ha_state()

    @property
    def state_attributes(self):
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
        self.hass.bus.remove_listener(EVENT_TIME_CHANGED, self.timer)
        self.timer = None

    def _timer_expired(self, now=None):
        """
        Event callback after countdown timer expires.

        Enable unoccupied scene, if configured for the current mode.
        """
        _LOGGER.info('timer expired %s', self)
        self.timer = None
        self.mode = STATE_NOT_OCCUPIED
        self.hass.services.call(DOMAIN, 'enable_unoccupied_scene', {
            'entity_id': self.entity_id
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
        _LOGGER.debug('rfid %s state is %s', rfid_sensor, location)
        hass.services.call(DEVICE_TRACKER_DOMAIN, SERVICE_SEE, {
            ATTR_DEV_ID: split_entity_id(rfid_sensor)[1],
            ATTR_LOCATION_NAME: location,
        })

    helper.track_utc_time_change(hass, rfid_seen, second=0)

    def rfid_state_change(entity_id, old_state, new_state):
        """ Calls see service immediately with state of RFID sensor. """
        rfid_seen()

    helper.track_state_change(hass, rfid_sensor, rfid_state_change)


def setup(hass, config):
    """ Setup myhome component. """

    home = MyHome(hass)
    room_conf = config[DOMAIN].get(CONF_ROOMS, {})
    for name, conf in room_conf.items():
        room = create_room(hass, name, conf)
        room.update_ha_state()
        home.add(room)
        # hide all the scenes related to this room
        for name in hass.states.entity_ids(DOMAIN_SCENE):
            if name.startswith('{}.{}'.format(DOMAIN_SCENE, room.name.lower())):
                Entity.overwrite_attribute(name, [ATTR_HIDDEN], [True])
                state = hass.states.get(name)
                hass.states.set(name, state, {ATTR_HIDDEN: True})

    register_room_services(hass, home)

    home.update_ha_state()
    _LOGGER.info('myhome loaded: %s', home)

    register_presence_handlers(hass, config)
    _LOGGER.info('registered presense handlers')

    return True
