import datetime
import appdaemon.plugins.hass.hassapi as hass

STATE_OCCUPIED = 'occupied'
STATE_ON = 'on'
STATE_OFF = 'off'
STATE_MOVIE = 'Movie'
STATE_TV = 'TV'


class AutoLight(hass.Hass):
    """
    Automatically update lights based on external conditions.
    - Home mode (time of day)
    - Media mode
    - Room occupancy
    - Light levels
    """
    def initialize(self):
        time = datetime.time(0, 0, 0)
        self.modes = self.args['modes']
        self.entities = self.args['entities']
        self.home = self.get_app('homemode')
        self.sensors = self.args.get('sensors', {})
        self.media = self.args.get('media', {})
        if self.media:
            self.listen_state(self.on_media_change, self.media['mode'])
        self.run_minutely(self.on_schedule, time)
        self.listen_state(self.on_occupancy_change, self.sensors['presence'])
        self.log('initialized')

    def calculate_attr(self, begin, end, easing):
        """
        Returns a calculated attribute given a begin state, end state,
        and easing function
        """
        if isinstance(begin, (int, float)):
            change = end - begin
            attr = easing(self.home.current, begin, change, self.home.duration)
            if isinstance(begin, int):
                return round(int(attr))
            return float('{0:.4f}'.format(attr))
        if isinstance(begin, (list, tuple)):
            return [self.calculate_attr(b, e, easing) for b, e in zip(begin, end)]
        return None

    def get_brightness(self, bri):
        """Vary the brightness based on the distance to the current threshold"""
        bri = int(bri)
        threshold = self.current_threshold
        light_pct = self.current_light_level
        adj = int(bri / threshold * (threshold - light_pct))
        if self.media:
            current = self.current_media_mode
            if current in self.media:
                self.log('media mode:{} adj:{} limit:{}'.format(current, adj, self.media[current]))
                adj = min(adj, self.media[current])
        adj = max(adj, 1)
        self.log('bri:{} adj:{} threshold:{} light:{}'.format(bri, adj, threshold, light_pct))
        return adj

    def get_transition(self, state, new_state, trigger=None):
        """
        Return the transition time for different update triggers.
        Triggers:
        - occupancy: transition immediately
        - media: transition slowly based on state
        """
        if trigger == 'media' and self.current_media_mode not in (STATE_MOVIE, STATE_TV):
            return 3
        if new_state == STATE_ON and trigger == 'occupancy':
            return 1
        return 10

    @property
    def current_threshold(self):
        return int(self.get_state(self.sensors['threshold']))

    @property
    def current_light_level(self):
        return int(self.get_state(self.sensors['light']))

    @property
    def current_media_mode(self):
        return self.get_state(self.media['mode'])

    @property
    def should_auto_update(self):
        """
        Returns True if this light should currently be updated.
        Update conditions:
        - there is no manual override (switch)
        - the room is occupied (presence)
        - the current mode is configured for this light
        """
        enabled = True
        if 'switch' in self.sensors:
            enabled = self.get_state(self.sensors['switch']) == STATE_ON
        occupied = self.get_state(self.sensors['presence']) == STATE_OCCUPIED
        configured = self.home.mode in self.modes
        self.log('enabled:{} occupied:{} configured:{}'.format(enabled, occupied, configured))
        return enabled and occupied and configured

    @property
    def desired_state(self):
        """
        The light should be on if:
        - the light threshold is below the configured threshold
        - the light is already on but the light threshold has not exceeded the hysterisis threshold
        - the media mode is not "Movie" (media)

        The light should be off if:
        - the light threshold is above the configured threshold
        - the media mode is "Movie" (media)
        """
        dark = self.current_light_level < self.current_threshold
        movie = self.current_media_mode == STATE_MOVIE
        self.log('dark:{} movie:{}'.format(dark, movie))
        if dark and not movie:
            return STATE_ON
        return STATE_OFF

    @property
    def desired_state_attrs(self):
        """
        Returns a dict of desired state attributes based on the current and
        next home modes.
        """
        mode = self.home.mode
        next_mode = self.home.next_mode
        if mode not in self.modes:
            return {}
        start = self.modes[mode]
        end = self.modes.get(next_mode, start)
        easing = getattr(self, start.get('easing', 'in_out_quad'))
        attrs = {}
        self.log('mode:{} next:{}'.format(mode, next_mode), level="DEBUG")
        for attr in start:
            if attr == 'easing':
                continue
            attrs[attr] = self.calculate_attr(start[attr], end[attr], easing)
            if attr == 'brightness':
                attrs[attr] = self.get_brightness(attrs[attr])
            self.log('attr:{} start:{} end:{} result:{}'.format(
                attr, start[attr], end[attr], attrs[attr]), level="DEBUG")
        self.log(
            'current:{} duration:{} easing:{}'.format(
                self.home.current,
                self.home.duration,
                easing.__name__,
            ),
            level="DEBUG",
        )
        return attrs

    def update_lights(self, trigger=None):
        """Updates the configured light entities with the desired state"""
        if not self.should_auto_update:
            self.log('not updating')
            return
        for entity_id in self.entities:
            state = self.get_state(entity_id)
            new_state = self.desired_state
            attrs = self.desired_state_attrs
            attrs['transition'] = self.get_transition(state, new_state, trigger)
            self.log('entity_id:{} state:{} desired:{} attrs:{}'.format(
                entity_id, state, new_state, attrs))
            if new_state == STATE_ON:
                self.call_service('light/turn_on', entity_id=entity_id, **attrs)
            else:
                self.call_service('light/turn_off', entity_id=entity_id,
                                  transition=attrs['transition'])

    def on_schedule(self, kwargs):
        self.log('update schedule:{}'.format(kwargs))
        self.update_lights()

    def on_media_change(self, entity, attribute, old, new, kwargs):
        self.log('update media entity:{} attribute:{} old:{} new:{} kwargs:{}'.format(entity, attribute, old, new, kwargs))
        self.update_lights(trigger='media')

    def on_occupancy_change(self, entity, attribute, old, new, kwargs):
        self.log('update occupancy entity:{} attribute:{} old:{} new:{} kwargs:{}'.format(entity, attribute, old, new, kwargs))
        self.update_lights(trigger='occupancy')

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
