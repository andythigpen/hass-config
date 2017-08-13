"""
Hotword detector
"""
import sys
import snowboy

from homeassistant.const import EVENT_HOMEASSISTANT_STOP

# fix import path for snowboy
sys.path.extend(snowboy.__path__._path)

import snowboydecoder

DOMAIN = 'myvoice'
CONF_MODEL = 'model'
CONF_SENSITIVITY = 'sensitivity'
EVENT_DETECTED = 'detected'


def setup(hass, config):
    """Sets up the hotword detector"""
    model = config[DOMAIN].get(CONF_MODEL, 'resources/alexa.umdl')
    sensitivity = config[DOMAIN].get(CONF_SENSITIVITY, [])
    audio_gain = config[DOMAIN].get(CONF_AUDIO_GAIN, 1)

    detector = snowboydecoder.HotwordDetector(
        model, sensitivity=sensitivity, audio_gain=audio_gain)
    shutting_down = False

    def detected():
        """Fires an event when the keyword is detected"""
        hass.bus.fire('{}.{}'.format(DOMAIN, EVENT_DETECTED))

    def stop_detector(event):
        """Stops the detector instance on shutdown"""
        shutting_down = True
        detector.terminate()

    def interrupt_callback():
        """Called periodically by the detector.  Return True to stop."""
        return shutting_down

    detector.start(detected_callback=detected,
                   interrupt_check=interrupt_callback,
                   sleep_time=0.03)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_detector)
