import datetime
import appdaemon.plugins.hass.hassapi as hass

STATE_OCCUPIED = 'occupied'
STATE_COUNTDOWN = 'countdown'
STATE_NOT_OCCUPIED = 'not_occupied'
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
        self.sensors = self.args.get('sensors', {})
        self.media = self.args.get('media', None)
        if self.media:
            self.listen_state(self.on_media_change, self.media)
        self.brightness = self.args.get('brightness', {})
        if self.brightness.get('entity_id'):
            self.listen_state(self.on_brightness_change,
                              self.brightness['entity_id'])
        self.run_minutely(self.on_schedule, time)
        self.listen_state(self.on_occupancy_change, self.sensors['presence'])
        self.listen_state(self.on_auto_update_change,
                          self.sensors['auto_update'])
        self.listen_state(self.reenable_auto_update,
                          self.sensors['auto_update'],
                          new=STATE_ON,
                          duration=60 * 60 * 5)

        for entity_id in self.entities:
            self.listen_state(self.on_state_change, entity_id,
                              attribute='context')
        self.log('initialized')

    def get_autolight_entity(self, entity_id):
        return 'autolight.{}'.format(self.split_entity(entity_id)[1])

    def calculate_attr(self, begin, end, easing):
        """
        Returns a calculated attribute given a begin state, end state,
        and easing function
        """
        if isinstance(begin, (int, float)):
            attr = easing(begin, end)
            if isinstance(begin, int):
                return round(int(attr))
            return float('{0:.4f}'.format(attr))
        if isinstance(begin, (list, tuple)):
            return [
                self.calculate_attr(b, e, easing) for b, e in zip(begin, end)
            ]
        return None

    def get_brightness(self, bri):
        """
        Vary the brightness based on the distance to the current threshold
        and an optionally configured entity that limits the max brightness
        based on the entity's state.
        """
        bri = int(bri)
        threshold = self.current_threshold
        light_pct = self.current_light_level
        minimum = self.brightness.get('min', 0)
        adj = int(bri / threshold * threshold - max(light_pct - minimum, 0))
        if self.brightness.get('entity_id'):
            current = self.get_state(self.brightness['entity_id'])
            self.log('current:{} brightness:{}'.format(
                current, self.brightness), level='DEBUG')
            states = self.brightness['states']
            if current in states:
                self.log('current:{} adj:{} limit:{}'.format(
                    current, adj, states[current]), level='DEBUG')
                adj = min(adj, states[current])
        adj = max(adj, 1)
        self.log('bri:{} adj:{} threshold:{} light:{} min:{}'.format(
            bri, adj, threshold, light_pct, minimum), level='DEBUG')
        return adj

    def get_transition(self, state, new_state, trigger=None):
        """
        Return the transition time for different update triggers.
        Triggers:
        - occupancy: transition immediately
        - media: transition slowly based on state
        """
        if trigger == 'media' and self.current_media_mode not in (STATE_MOVIE,
                                                                  STATE_TV):
            return 3
        if new_state == STATE_ON and trigger == 'occupancy':
            return 1
        return 10

    def get_switch_state(self, entity_id):
        """
        Returns True if the entity state is 'on'.
        If the entity_id starts with '!', then the inverse is returned.
        """
        state = STATE_ON
        if entity_id.startswith('!'):
            state = STATE_OFF
            entity_id = entity_id[1:]
        return self.get_state(entity_id) == state

    @property
    def home(self):
        return self.get_app('homemode')

    @property
    def auto_update(self):
        return self.get_state(self.sensors['auto_update']) == STATE_ON

    @auto_update.setter
    def auto_update(self, value):
        if value:
            svc = 'input_boolean/turn_on'
        else:
            svc = 'input_boolean/turn_off'
        self.call_service(svc, entity_id=self.sensors['auto_update'])

    @property
    def current_threshold(self):
        return int(self.get_state(self.sensors['threshold']))

    @property
    def current_light_level(self):
        return int(self.get_state(self.sensors['light']))

    @property
    def current_media_mode(self):
        if self.media:
            return self.get_state(self.media)
        return None

    @property
    def should_auto_update(self):
        """
        Returns True if this light should currently be updated.
        Update conditions:
        - there is no manual override (switch)
        - the current mode is configured for this light
        - the presence sensor is not in countdown mode
        """
        if not self.auto_update:
            self.log('auto update is off', level='WARNING')
            return False
        enabled = True
        if 'switch' in self.sensors:
            if isinstance(self.sensors['switch'], (list, tuple)):
                enabled = all([
                    self.get_switch_state(n) for n in self.sensors['switch']
                ])
            else:
                enabled = self.get_switch_state(self.sensors['switch'])
        configured = self.home.mode in self.modes
        countdown = self.get_state(self.sensors['presence']) == STATE_COUNTDOWN
        self.log('enabled:{} configured:{} countdown:{}'.format(
            enabled, configured, countdown), level='DEBUG')
        return enabled and configured and not countdown

    @property
    def desired_state(self):
        """
        The light should be on if:
        - the light threshold is below the configured threshold
        - the light is already on but the light threshold has not exceeded the
          hysteresis threshold
        - the media mode is not "Movie" (media)
        - the room is occupied (presence)

        The light should be off if:
        - the light threshold is above the configured threshold
        - the media mode is "Movie" (media)
        - the room is not occupied (presence)
        """
        dark = self.current_light_level < self.current_threshold
        movie = self.current_media_mode == STATE_MOVIE
        occupied = self.get_state(self.sensors['presence']) == STATE_OCCUPIED
        self.log('dark:{} occupied:{} movie:{}'.format(dark, occupied, movie),
                 level='DEBUG')
        if dark and occupied and not movie:
            return STATE_ON
        return STATE_OFF

    @property
    def desired_state_attrs(self):
        """
        Returns a dict of desired state attributes based on the current and
        next home modes.
        """
        start, end = self.home.get_start_end(self.modes)
        if start is None:
            return {}
        if end is None:
            end = start
        app = self.get_app('modeeasing')
        easing = getattr(app, start.get('easing', 'in_out_quad'))
        attrs = {}
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
                easing,
            ),
            level="DEBUG",
        )
        return attrs

    def update_lights(self, trigger=None):
        """Updates the configured light entities with the desired state"""
        if not self.should_auto_update:
            self.log('not updating')
            return

        new_state = self.desired_state
        attrs = self.desired_state_attrs
        for entity_id in self.entities:
            state = self.get_state(entity_id)
            attrs['transition'] = self.get_transition(
                state, new_state, trigger)
            self.log('entity_id:{} state:{} desired:{} attrs:{}'.format(
                entity_id, state, new_state, attrs))
            if new_state == STATE_ON:
                self.call_service('light/turn_on', entity_id=entity_id,
                                  **attrs)
            else:
                self.call_service('light/turn_off', entity_id=entity_id,
                                  transition=attrs['transition'])

    def on_schedule(self, kwargs):
        """Callback for scheduled updates"""
        self.update_lights()

    def on_media_change(self, entity, attribute, old, new, kwargs):
        """Callback for media state changes"""
        self.update_lights(trigger='media')

    def on_occupancy_change(self, entity, attribute, old, new, kwargs):
        """Callback for occupancy state changes"""
        self.update_lights(trigger='occupancy')
        if not self.auto_update and new == STATE_NOT_OCCUPIED:
            self.log('enabling auto update due to occupancy change')
            self.auto_update = True

    def on_brightness_change(self, entity, attribute, old, new, kwargs):
        """Callback for brightness entity state changes"""
        self.update_lights(trigger='brightness')

    def on_auto_update_change(self, entity, attribute, old, new, kwargs):
        """Callback for auto update entity state changes"""
        if new == STATE_ON:
            self.update_lights(trigger='auto_update')

    def on_state_change(self, entity, attribute, old, new, kwargs):
        """Callback for tracked entity state changes"""
        user_id = new['user_id']
        if user_id is not None and user_id != self.config['user_id']:
            self.log('entity {} modified by {}'.format(entity, user_id),
                     level='WARNING')
            self.auto_update = False

    def reenable_auto_update(self, entity, attribute, old, new, kwargs):
        """Callback for auto update disabled timeout"""
        self.log('reenabling auto update after timeout')
        self.auto_update = True
