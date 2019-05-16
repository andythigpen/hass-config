import datetime
import appdaemon.plugins.hass.hassapi as hass


class AutoLight(hass.Hass):
    def initialize(self):
        time = datetime.time(0, 0, 0)
        self.modes = self.args['modes']
        self.home = self.get_app('homemode')
        self.run_minutely(self.update_light, time)
        self.log('initialized')

    def calculate_attr(self, begin, end, easing):
        """
        Returns a calculated attribute given a begin state, end state,
        and easing function
        """
        if isinstance(begin, (int, float)):
            change = end - begin
            self.log('current {} duration {}'.format(self.home.current, self.home.duration))
            attr = easing(self.home.current, begin, change, self.home.duration)
            if isinstance(begin, int):
                return round(int(attr))
            return float('{0:.4f}'.format(attr))
        if isinstance(begin, (list, tuple)):
            return [self.calculate_attr(b, e, easing) for b, e in zip(begin, end)]
        return None

    def update_light(self, kwargs):
        mode = self.home.mode
        next_mode = self.home.next_mode
        if mode not in self.modes:
            return
        start = self.modes[mode]
        end = self.modes.get(next_mode, start)
        easing = getattr(self, start.get('easing', 'in_out_quad'))
        #{%- set bri = easing(start["brightness"], end["brightness"])|round|int -%}
        attrs = {}
        for attr in start:
            if attr == 'easing':
                continue
            attrs[attr] = self.calculate_attr(start[attr], end[attr], easing)
        self.log(attrs)

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
