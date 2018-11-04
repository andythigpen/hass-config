"""
Turns on a scene for a room dependent upon the current house mode.
"""

def set_scene(hass, data, logger):
    """
    Combines the room name, mode, and current house mode into a scene name.
    Data:
    - room: name of the room (slugified)
    - state: state of the room (slugified, ex: occupied, not_occupied)
    """
    room_name = data.get('room').lower()
    room_entity_id = 'room.{}'.format(room_name)

    mode = hass.states.get('input_select.myhome_mode')
    if not mode:
        logger.warning('myhome mode not available')
        return

    mode = mode.state.lower()
    room_state = data.get('state', None)
    if room_state is None:
        room_state = hass.states.get(room_entity_id)
        room_state = room_state.state

    scene_name = 'scene.{}_{}_{}'.format(room_name, mode, room_state)

    modifier = data.get('modifier', None)
    if modifier:
        scene_name = '{}_{}'.format(scene_name, modifier)

    if scene_name not in hass.states.entity_ids('scene'):
        logger.warning('no scene configured with name %s', scene_name)
        return

    logger.info('turning on scene %s for room %s', scene_name, room_name)
    hass.services.call('scene', 'turn_on', {'entity_id': scene_name})


set_scene(hass, data, logger)
