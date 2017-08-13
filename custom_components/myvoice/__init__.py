"""
myvoice - Offline voice recognition
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .const import (
    DOMAIN, CONF_MODEL, DEFAULT_MODEL, CONF_SENSITIVITY, DEFAULT_SENSITIVITY,
    CONF_AUDIO_GAIN, DEFAULT_AUDIO_GAIN, EVENT_DETECTED)
from .detect import setup as detect_setup


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
        vol.Optional(CONF_SENSITIVITY, default=DEFAULT_SENSITIVITY): cv.small_float,
        vol.Optional(CONF_AUDIO_GAIN, default=DEFAULT_AUDIO_GAIN): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    detect_setup(hass, config)

    def handle_event(event):
        print(event)

    hass.bus.listen(EVENT_DETECTED, handle_event)
    return True
