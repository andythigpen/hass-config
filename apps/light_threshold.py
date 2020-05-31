import datetime
import hassapi as hass


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
        self.log('start:{} end:{} mode:{}'.format(start, end, home.mode),
                 level='INFO')
        if start is None:
            start = self.default
        if end is None:
            end = start
        app = self.get_app('modeeasing')
        value = int(round(app.in_out_quad(start, end)))
        value = max(value, 0)
        self.log('value:{}'.format(value), level='INFO')
        self.set_value(self.entity_id, value)
