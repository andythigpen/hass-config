"""
custom_components.myhome
~~~~~~~~~~~~~~~~~~~~~~~~~

Custom rules/automation for my home
"""
import logging

from datetime import timedelta
from functools import partial

import homeassistant.util.dt as date_util
from homeassistant.components.sun import next_setting
import homeassistant.helpers.event as helper
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_NOT_HOME, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    ATTR_ENTITY_ID, EVENT_TIME_CHANGED)


DOMAIN = 'myhome'
ENTITY_ID = 'myhome.mode'
DEPENDENCIES = ['group', 'sun']

_LOGGER = logging.getLogger(__name__)


STATE_OCCUPIED = 'occupied'
STATE_NOT_OCCUPIED = 'not_occupied'
STATE_COUNTDOWN = 'countdown'

# default state, does nothing
STATE_MANUAL = 'manual'
# triggered by movement outside of bedroom > 6am
STATE_MORNING = 'morning'
STATE_DAY = 'day'
STATE_EVENING = 'evening'
STATE_NIGHT = 'night'
# after a certain time, lights will be turned on very dim (or not at all)
STATE_ASLEEP = 'asleep'

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


class MyHome(object):
    """
    Contains Room objects with sensors for tracking presence and performing
    actions based on location and "house mode".
    """
    def __init__(self, hass):
        self.hass = hass
        self.rooms = {}
        self.hass.states.set(ENTITY_ID, STATE_MANUAL)
        self.evening_offset = timedelta(hours=2)
        self.night_offset = timedelta(hours=1)

    def register_event_listeners(self):
        """ Adds event listeners to HA. """
        helper.track_state_change(self.hass,
            self.rooms.keys(), self.room_occupied, to_state=STATE_OCCUPIED)
        helper.track_state_change(self.hass,
            'group.all_devices', self.not_home, to_state=STATE_NOT_HOME)
        helper.track_time_change(self.hass,
            partial(self._set_mode_callback, STATE_MORNING),
            hour=6, minute=0, second=0)
        helper.track_time_change(self.hass,
            partial(self._set_mode_callback, STATE_DAY),
            hour=9, minute=0, second=0)
        helper.track_point_in_time(self.hass,
            self.sunset, next_setting(self.hass) - self.evening_offset)
        helper.track_point_in_time(self.hass,
            self.night, next_setting(self.hass) + self.night_offset)
        self.hass.services.register(DOMAIN, 'set_mode', self._set_mode_service)

    @property
    def mode(self):
        """ Returns the current myhome mode. """
        return self.hass.states.get(ENTITY_ID).state

    @mode.setter
    def mode(self, new_mode):
        """
        Sets the home mode, if the current mode is not STATE_MANUAL.

        STATE_MANUAL must be explicitly turned off.
        """
        if self.mode == STATE_MANUAL:
            return
        self.hass.states.set(ENTITY_ID, new_mode)

    def _set_mode_callback(self, mode, now):
        """ Event timer callback that sets the mode. """
        self.mode = mode

    def _set_mode_service(self, service):
        """ Service method for setting mode. """
        self.mode = service.data.get(ATTR_MODE)

    def sunset(self, now):
        """
        Event callback for before the sun sets.

        Sets the house mode to evening.
        """
        self.mode = STATE_EVENING

        def reschedule(now):
            """ Reschedules the sunset callback for the next sunset. """
            helper.track_point_in_time(self.hass,
                self.sunset, next_setting(self.hass) - self.evening_offset)

        helper.track_point_in_time(self.hass,
            reschedule, next_setting(self.hass) + timedelta(seconds=1))

    def night(self, now):
        """
        Event callback for after the sun sets.

        Sets the house mode to night.
        """
        self.mode = STATE_NIGHT

        helper.track_point_in_time(self.hass,
            self.night, next_setting(self.hass) + self.night_offset)

    def get(self, entity_id):
        """ Returns a Room, given an entity_id. """
        return self.rooms.get(entity_id)

    def room_occupied(self, entity_id, old_state, new_state):
        """
        Event callback for when a room changes state to STATE_OCCUPIED.

        Sets all other rooms that were STATE_OCCUPIED to STATE_COUNTDOWN.
        """
        _LOGGER.info('room_occupied %s %s', entity_id, new_state)
        for room in self.rooms.values():
            if room.entity_id == entity_id:
                continue
            if room.state.state != STATE_OCCUPIED:
                continue
            _LOGGER.info('room_occupied found room %s', room)
            room.start_timer()

    def not_home(self, entity_id, old_state, new_state):
        """
        Event callback for all devices from device_tracker.

        Sets all rooms to STATE_NOT_OCCUPIED when no one is home.
        """
        _LOGGER.info('not_home: setting all rooms to not occupied')
        for room in self.rooms.values():
            room.set_not_occupied()

    def add(self, room):
        """ Adds a room. """
        if room is not None:
            self.rooms[room.entity_id] = room

    def __repr__(self):
        return '<home: %s>' % self.rooms


class Room(object):
    """
    Contains motion and light sensors and performs actions based on them,
    the current house mode, and a person's location in the house.
    """
    def __init__(self, hass, name, motion, light, timeout, modes):
        self.name = name
        self.entity_id = '{}.{}'.format(DOMAIN_ROOM, name)
        self.hass = hass
        self.hass.states.set(self.entity_id, STATE_NOT_OCCUPIED)
        self.motion = motion
        self.light = light
        self.timeout = timeout
        self.timer = None
        self.modes = modes

    def register_event_listeners(self):
        """ Registers event listeners with HA so that we're notified. """
        helper.track_state_change(self.hass,
            self.motion, self.motion_detected,
            from_state=STATE_OFF, to_state=STATE_ON)
        helper.track_state_change(self.hass,
            self.entity_id, self.occupied,
            from_state=STATE_NOT_OCCUPIED, to_state=STATE_OCCUPIED)

    @property
    def state(self):
        """ Returns the current room state (occupied/not_occupied). """
        return self.hass.states.get(self.entity_id)

    def start_timer(self):
        """
        Registers a countdown timer that will trigger no occupancy when fired.
        Sets the state to STATE_COUNTDOWN.
        """
        if self.timer is not None:
            return
        self.timer = helper.track_point_in_utc_time(self.hass,
            self.not_occupied, date_util.utcnow() + self.timeout)
        self.hass.states.set(self.entity_id, STATE_COUNTDOWN)
        _LOGGER.info('room_occupied set timer %s', self)

    def disable_timer(self):
        """ Unregisters the timer, if set. """
        if self.timer is None:
            return
        _LOGGER.info('canceling timer %s', self)
        self.hass.bus.remove_listener(EVENT_TIME_CHANGED, self.timer)
        self.timer = None

    def set_not_occupied(self):
        """ Sets the room to currently unoccupied. """
        self.hass.states.set(self.entity_id, STATE_NOT_OCCUPIED)
        self.disable_timer()

    def motion_detected(self, entity_id, old_state, new_state):
        """
        Event callback when motion is detected.

        Disables the countdown timer if set for this room.
        Sets the current state of this room to STATE_OCCUPIED.
        """
        devices = self.hass.states.get('group.all_devices')
        if devices and devices.state == STATE_NOT_HOME:
            _LOGGER.warning('%s motion but no one is home', entity_id)
            return
        _LOGGER.info('motion %s', new_state)
        self.disable_timer()
        self.hass.states.set(self.entity_id, STATE_OCCUPIED)

    def get_mode_config(self):
        """
        Returns the config for the current mode, or None if the current mode
        has no config.
        """
        home_mode = self.hass.states.get(ENTITY_ID)
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
            conf[ATTR_ENTITY_ID] = 'group.{}'.format(self.name)
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

    def occupied(self, entity_id, old_state, new_state):
        """
        Event callback when room becomes occupied.

        Turns the lights on if one of the light sensors is below its threshold
        and the current mode is configured to do so.
        """
        _LOGGER.info('occupied: %s', self)
        mode = self.get_mode_config()
        data_on = self.get_light_data(mode, CONF_OCCUPIED)
        if data_on is None:
            _LOGGER.info('occupied: no configuration for current mode')
            return
        for sensor_id, sensor in self.light.items():
            entity = self.hass.states.get(sensor_id)
            if not entity:
                _LOGGER.warning('occupied: light sensor %s not found',
                                sensor_id)
                continue
            if entity.state is None or len(entity.state) == 0:
                _LOGGER.warning('occupied: no state for %s', sensor_id)
                continue
            _LOGGER.info('light sensor [%s], low threshold [%s]',
                         int(entity.state), sensor[CONF_LOW])
            if mode.get(CONF_THRESHOLD, True):
                if int(entity.state) >= sensor[CONF_LOW]:
                    _LOGGER.info('light sensor [%s] above threshold [%s]',
                                 int(entity.state), sensor[CONF_LOW])
                    continue
            _LOGGER.info('occupied: turning on: %s', data_on)
            self.hass.services.call(DOMAIN_LIGHT, SERVICE_TURN_ON, data_on)
            return

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
        room.register_event_listeners()
        home.add(room)

    home.register_event_listeners()
    _LOGGER.info('myhome loaded: %s', home)

    return True
