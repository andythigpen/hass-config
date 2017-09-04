"""
Sets the room to the given state.
"""

def get_icon(state):
    """Return the icon based upon the current mode."""
    if state == 'occupied':
        return 'mdi:account'
    elif state == 'not_occupied':
        return 'mdi:account-outline'
    elif state == 'countdown':
        return 'mdi:clock'
    return 'mdi:home-variant'


def update_room_occupancy(hass, entity_id):
    """Sets any occupied rooms to countdown, except entity_id"""
    global set_state
    for room_id in hass.states.entity_ids('room'):
        if room_id == entity_id:
            continue
        state = hass.states.get(room_id)
        if state.state == 'occupied':
            set_state(hass, room_id, 'countdown')


def set_state(hass, entity_id, new_state):
    """Sets the state and the icon for the room"""
    global get_icon, update_room_occupancy
    state = hass.states.get(entity_id)
    if state is not None:
        attrs = state.attributes.copy()
    else:
        attrs = {}
    attrs['icon'] = get_icon(new_state)
    hass.states.set(entity_id, new_state, attrs)

    if new_state == 'occupied':
        update_room_occupancy(hass, entity_id)


entity_id = data.get('entity_id')
state = data.get('state')

set_state(hass, entity_id, state)
