"""
Sets all rooms to STATE_NOT_OCCUPIED when no one is home.
"""

for room_id in hass.states.entity_ids('room'):
    state = hass.states.get(room_id)
    hass.services.call('python_script', 'set_room_state', {
        'entity_id': room_id,
        'state': 'not_occupied',
    })
