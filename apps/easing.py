from functools import partialmethod
import appdaemon.appapi as appapi


class Easing(appapi.AppDaemon):
    """
    Easing functions from https://easings.net/ and
    http://robertpenner.com/easing/
    t: current time
    b: beginning value
    c: change in value
    d: duration
    """
    def initialize(self):
        pass

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


class ModeEasing(Easing):
    """
    Helper methods for easing functions based on home modes
    """
    def initialize(self):
        self.home = self.get_app('homemode')

    def _easing(self, name, b, e):
        c = e - b
        method = getattr(super(), name)
        return method(self.home.current, b, c, self.home.duration)

    in_quad = partialmethod(_easing, 'in_quad')
    in_out_quad = partialmethod(_easing, 'in_out_quad')
    out_quad = partialmethod(_easing, 'out_quad')
