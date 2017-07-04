"""
Updates the mode icon in the interface based on the mode selection.
"""

icons = {
    'morning': 'mdi:weather-sunset-up',
    'day': 'mdi:weather-sunny',
    'afternoon': 'mdi:weather-sunny',
    'evening': 'mdi:weather-sunset-down',
    'night': 'mdi:weather-night',
    'asleep': 'mdi:sleep',
}

mode = hass.states.get('input_select.myhome_mode')
attrs = mode.attributes.copy()
attrs['icon'] = icons.get(mode.state.lower(), 'mdi:home-variant')
hass.states.set('input_select.myhome_mode', mode.state, attributes=attrs)
