"""
Turns on a scene for a room dependent upon the current house mode.
"""

def set_scene(hass, data, logger):
    """
    Combines the room name, mode, and current house mode into a scene name.
    Data:
    - room: name of the room (slugified)
    - mode: mode of the room (slugified, ex: occupied, not_occupied)
    """
    room_name = data.get('room').lower()
    room_entity_id = 'room.{}'.format(room_name)
    if not hass.states.is_state(room_entity_id, 'on'):
        logger.info('Room %s not found or not enabled', room_name)
        return

    mode = hass.states.get('input_select.myhome_mode')
    if not mode:
        logger.warning('myhome mode not available')
        return

    mode = mode.state.lower()
    room_mode = data.get('mode', None)
    if room_mode is None:
        room_state = hass.states.get(room_entity_id)
        room_mode = room_state.attributes['mode']

    scene_name = 'scene.{}_{}_{}'.format(room_name, mode, room_mode)
    if scene_name not in hass.states.entity_ids('scene'):
        logger.warning('no scene configured with name %s', scene_name)
        return

    logger.info('turning on scene %s for room %s', scene_name, room_name)
    hass.services.call('scene', 'turn_on', {'entity_id': scene_name})


set_scene(hass, data, logger)
