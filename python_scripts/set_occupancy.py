"""
Sets a room occupancy input_boolean to the given state.
"""

def set_state(hass, entity_id):
    """Turns on the input_boolean and turns off all other occupancy input booleans"""

    hass.services.call('input_boolean', 'turn_on', {
        'entity_id': entity_id,
    })

    for boolean_id in hass.states.entity_ids('input_boolean'):
        if boolean_id == entity_id or not boolean_id.endswith('_occupied'):
            continue
        hass.services.call('input_boolean', 'turn_off', {'entity_id': boolean_id})


entity_id = data.get('entity_id')
set_state(hass, entity_id)
