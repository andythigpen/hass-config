"""
Support for iCalendar.
"""
import copy
import logging
from datetime import datetime, timedelta

import voluptuous as vol
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT, PLATFORM_SCHEMA, CalendarEventDevice,
    extract_offset, is_offset_reached,
)
from homeassistant.util import Throttle

REQUIREMENTS = ['icalevents==0.1.13']

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_ID = 'device_id'
DEFAULT_CALENDAR_NAME = 'calendar'
OFFSET = "!!"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_URL): vol.Url(),
})

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


def setup_platform(hass, config, add_entities, disc_info=None):
    url = config.get(CONF_URL)
    name = config.get(CONF_NAME, DEFAULT_CALENDAR_NAME)
    entity_id = generate_entity_id(ENTITY_ID_FORMAT, name, hass=hass)
    add_entities([
        ICalendarEventDevice(name, entity_id, url),
    ])


class ICalendarData:
    def __init__(self, url):
        self.url = url
        self.events = []
        self.event = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        from icalevents import icalevents
        events = icalevents.events(self.url, start=datetime.now())
        if not events:
            self.events = []
            self.event = None
            return True
        sorted_events = sorted(events, key=lambda ev: ev.start)
        self.events = list(map(self.convert_event, sorted_events))
        self.event = self.events[0]
        return True

    def convert_event(self, event):
        """Return a dict formatted event."""
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
        return {
            'start': start,
            'end': end,
            'summary': event.summary,
            'location': '',
            'description': event.description,
        }


class ICalendarEventDevice(CalendarEventDevice):
    def __init__(self, name, entity_id, url):
        self.data = ICalendarData(url)
        self.entity_id = entity_id
        self._name = name
        self._event = None
        self._offset_reached = False

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {"offset_reached": self._offset_reached}

    @property
    def event(self):
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self):
        """Return the name of this entity."""
        return self._name

    def update(self):
        self.data.update()
        event = copy.deepcopy(self.data.event)
        if event is None:
            self._event = event
            return
        event = extract_offset(event["summary"], OFFSET)
        self._offset_reached = is_offset_reached(event)
        self._event = event

    async def async_get_events(self, hass, start_date, end_date):
        """Return calendar events within a datetime range."""
        return self.data.events
