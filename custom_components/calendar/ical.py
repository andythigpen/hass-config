"""
Support for iCalendar.
"""
from datetime import datetime, timedelta
import logging
import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.components.calendar import (
    PLATFORM_SCHEMA, CalendarEventDevice,
)
from homeassistant.util import Throttle

REQUIREMENTS = ['icalevents==0.1.13']

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = 'device_id'
DEFAULT_CALENDAR_NAME = 'calendar'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): vol.Url(),
})

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


def setup_platform(hass, config, add_entities, disc_info=None):
    url = config.get(CONF_URL)
    name = config.get(CONF_NAME, DEFAULT_CALENDAR_NAME)
    device_data = {
        CONF_NAME: name,
        CONF_DEVICE_ID: name,
    }
    add_entities([
        ICalendarEventDevice(hass, device_data, url),
    ])


class ICalendarData:
    def __init__(self, url):
        self.url = url
        self.event = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        from icalevents import icalevents
        events = icalevents.events(self.url, start=datetime.now())
        if not events:
            self.event = None
            return True
        event = events[0]
        if event.all_day:
            start = {
                'date': str(event.start.date()),
            }
            end = {
                'date': str(event.end.date()),
            }
        else:
            start = {
                'dateTime': str(event.start),
            }
            end = {
                'dateTime': str(event.end),
            }
        self.event = {
            'start': start,
            'end': end,
            'summary': event.summary,
            'location': '',
            'description': event.description,
        }
        return True


class ICalendarEventDevice(CalendarEventDevice):
    def __init__(self, hass, device_data, url):
        self.data = ICalendarData(url)
        super().__init__(hass, device_data)
