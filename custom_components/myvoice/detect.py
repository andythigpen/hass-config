"""
Hotword detector
"""
import asyncio
import logging
import os
import sys
import time
import snowboy

# fix import path for snowboy
sys.path.extend(snowboy.__path__._path)
import snowboydecoder

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from .const import (
    DOMAIN, CONF_MODEL, CONF_SENSITIVITY, CONF_AUDIO_GAIN, EVENT_DETECTED)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Sets up the hotword detector"""
    model = config[DOMAIN].get(CONF_MODEL)
    if model is None:
        model = os.path.join(os.path.dirname(__file__), 'resources',
                             'alexa.umdl')
    sensitivity = config[DOMAIN].get(CONF_SENSITIVITY)
    if sensitivity is None:
        sensitivity = []
    audio_gain = config[DOMAIN].get(CONF_AUDIO_GAIN)

    detector = snowboydecoder.HotwordDetector(
        model, sensitivity=sensitivity, audio_gain=audio_gain)
    shutting_down = False

    def detected(hotword=None):
        """Fires an event when the keyword is detected"""
        hass.bus.fire(EVENT_DETECTED, {'hotword': hotword})

    @asyncio.coroutine
    def detect_job():
        if shutting_down:
            return
        data = detector.ring_buffer.get()
        if len(data) == 0:
            yield from asyncio.sleep(0.03)
            hass.async_add_job(detect_job)
            return

        ans = detector.detector.RunDetection(data)
        if ans == -1:
            _LOGGER.warning("Error initializing streams or reading audio data")
        elif ans > 0:
            message = "Keyword " + str(ans) + " detected at time: "
            message += time.strftime("%Y-%m-%d %H:%M:%S",
                                     time.localtime(time.time()))
            _LOGGER.info(message)
            detected(ans - 1)
        hass.async_add_job(detect_job)

    def stop_detector(event):
        """Stops the detector instance on shutdown"""
        shutting_down = True
        detector.terminate()

    hass.async_add_job(detect_job)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_detector)
    return True
