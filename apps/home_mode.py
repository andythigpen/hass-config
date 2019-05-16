import datetime
from collections import OrderedDict
import appdaemon.plugins.hass.hassapi as hass

ENTITY_ID = 'input_select.myhome_mode'


class HomeMode(hass.Hass):
    def initialize(self):
        self.modes = OrderedDict([
            (mode['name'], mode) for mode in self.args['modes']
        ])

    @property
    def mode(self):
        """Returns the next scheduled home mode"""
        return self.get_state(ENTITY_ID)

    @property
    def next_mode(self):
        """Returns the next scheduled home mode"""
        names = list(self.modes.keys())
        index = names.index(self.mode)
        nextmode = names[(index + 1) % len(names)]
        return nextmode

    def parse_time(self, time):
        """Parses a time string and returns a time object"""
        return datetime.time(*(int(part) for part in str(time).split(':')))

    @property
    def start(self):
        """Returns the start datetime of the current mode"""
        if self.mode not in self.modes:
            return 0
        return datetime.datetime.combine(
            datetime.datetime.now(),
            self.parse_time(self.modes[self.mode]["start"]),
        )

    @property
    def end(self):
        """Returns the end datetime of the current mode"""
        if self.mode not in self.modes:
            return 0
        return datetime.datetime.combine(
            datetime.datetime.now(),
            self.parse_time(self.modes[self.mode]["end"]),
        )

    @property
    def duration(self):
        """Returns the duration of the current mode"""
        if self.mode not in self.modes:
            return 1
        return (self.end - self.start).total_seconds()

    @property
    def current(self):
        """Returns the current offset of the current mode"""
        if self.mode not in self.modes:
            return 1
        return (datetime.datetime.now().replace(tzinfo=None) - self.start).total_seconds()