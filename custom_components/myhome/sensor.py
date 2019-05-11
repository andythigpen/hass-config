"""
Light mode sensor
"""
import logging
from collections import OrderedDict

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_MODE, CONF_SENSORS, CONF_ENTITIES
from homeassistant.components.light import LIGHT_TURN_ON_SCHEMA
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'myhome'

CONF_MODIFIERS = 'modifiers'
CONF_EASING = 'easing'
CONF_NEXT_MODE = 'next_mode'
CONF_MODE_START = 'mode_start'
CONF_MODE_END = 'mode_end'

SENSOR_SCHEMA = vol.Schema(LIGHT_TURN_ON_SCHEMA.extend({
    vol.Required(CONF_MODE): cv.string,
    vol.Required(CONF_EASING): cv.string,
}))
SENSORS_SCHEMA = vol.All(
    cv.ensure_list,
    [SENSOR_SCHEMA],
)
ENTITIES_SCHEMA = vol.Schema({
    vol.Required(CONF_MODE): cv.entity_id,
    vol.Required(CONF_NEXT_MODE): cv.entity_id,
    vol.Required(CONF_MODE_START): cv.entity_id,
    vol.Required(CONF_MODE_END): cv.entity_id,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSORS_SCHEMA),
    vol.Required(CONF_ENTITIES): ENTITIES_SCHEMA,
    #vol.Optional(CONF_MODIFIERS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup light mode sensors"""
    _LOGGER.info('setting up myhome sensors')
    sensors = []
    entities = config[CONF_ENTITIES]
    for name, device_config in config[CONF_SENSORS].items():
        _LOGGER.info('device %s', name)
        sensors.append(LightModeSensor(hass, name, device_config, entities))
    if sensors:
        add_devices(sensors)

    #def handle_info(call):
    #    """Handle the service call."""
    #    #name = call.data.get(ATTR_NAME, DEFAULT_NAME)
    #    _LOGGER.info('%s', [
    #        sensor.
    #    ])

    #hass.services.register(DOMAIN, 'info', handle_info)


class LightModeSensor(Entity):
    """Representation of a light mode sensor."""
    def __init__(self, hass, name, config, entities):
        self.hass = hass
        self._name = name
        self._entities = entities
        self._modes = OrderedDict([
            (mode[CONF_MODE], mode) for mode in config
        ])
        _LOGGER.info('modes %s', self._modes)
        _LOGGER.info('entities %s', self._entities)
        self._state = None

    """
    Easing functions from https://easings.net/ and http://robertpenner.com/easing/
    t: current time
    b: beginning value
    c: change in value
    d: duration
    """
    def in_quad(self, t, b, c, d):
        t = t / d
        return c * (t ** 2) + b

    def in_out_quad(self, t, b, c, d):
        t = t / d * 2
        if t < 1:
            return c / 2 * t * t + b
        return -c / 2 * ((t - 1) * (t - 3) - 1) + b

    def out_quad(self, t, b, c, d):
        t = t / d
        return -c * t * (t - 2) + b

    @property
    def mode_start(self):
        """Returns the start datetime of the current mode"""
        state = self.hass.states.get(self._entities[CONF_MODE_START])
        time = dt_util.parse_time(state.state)
        if not time:
            return None
        return dt_util.dt.datetime.combine(dt_util.now(), time)

    @property
    def mode_end(self):
        """Returns the end datetime of the current mode"""
        state = self.hass.states.get(self._entities[CONF_MODE_END])
        time = dt_util.parse_time(state.state)
        if not time:
            return None
        return dt_util.dt.datetime.combine(dt_util.now(), time)

    @property
    def duration(self):
        """Returns the duration of the current mode"""
        return (self.mode_end - self.mode_start).total_seconds()

    @property
    def current_offset(self):
        """Returns the offset in the current mode"""
        return (dt_util.now().replace(tzinfo=None) - self.mode_start).total_seconds()

    @property
    def current_mode(self):
        """Returns the current home mode"""
        state = self.hass.states.get(self._entities[CONF_MODE])
        if state.state in self._modes:
            return self._modes[state.state]
        return None

    @property
    def next_mode(self):
        """Returns the next home mode"""
        state = self.hass.states.get(self._entities[CONF_NEXT_MODE])
        if state.state in self._modes:
            return self._modes[state.state]
        return None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def calculate_attr(self, begin, end, easing):
        """Returns a calculated attribute given a begin state, end state, and easing function"""
        _LOGGER.info("%s %s %s %s", begin, end, easing, type(begin))
        if isinstance(begin, (int, float)):
            change = end - begin
            attr = easing(self.current_offset, begin, change, self.duration)
            if isinstance(begin, int):
                return round(int(attr))
            return attr
        if isinstance(begin, (list, tuple)):
            return [self.calculate_attr(b, e, easing) for b, e in zip(begin, end)]
        return None

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""
        mode = self.current_mode
        next_mode = self.next_mode
        if mode is None or next_mode is None:
            return {}

        attrs = {}
        easing = getattr(self, mode[CONF_EASING])
        for attr in mode:
            if attr in (CONF_MODE, CONF_EASING):
                continue
            if attr not in next_mode:
                continue
            attrs[attr] = self.calculate_attr(mode[attr], next_mode[attr], easing)
        #attrs.update({
        #    'start': self.mode_start,
        #    'end': self.mode_end,
        #    'duration': self.duration,
        #    'offset': self.current_offset,
        #    'mode': self.current_mode,
        #    'next': self.next_mode,
        #})
        return attrs

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.info('!!! update %s', self.device_state_attributes)
