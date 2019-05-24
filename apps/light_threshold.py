import datetime
import appdaemon.plugins.hass.hassapi as hass


class LightThreshold(hass.Hass):
    """
    Automatically update a state periodically based on:
    - Home mode (time of day)
    """
    def initialize(self):
        self.entity_id = self.args['entity_id']
        self.modes = self.args['modes']
        self.default = self.args['default']
        time = datetime.time(0, 0, 0)
        self.run_minutely(self.on_schedule, time)

    def on_schedule(self, kwargs):
        """Callback for scheduled updates"""
        home = self.get_app('homemode')
        start, end = home.get_start_end(self.modes)
        if start is None:
            start = self.default
        if end is None:
            end = start
        app = self.get_app('modeeasing')
        value = int(app.in_out_quad(start, end))
        self.set_value(self.entity_id, value)
