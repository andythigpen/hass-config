"""
Renders the scene template for all occupied rooms.
"""

def set_scene(hass, data, logger):
    """
    Triggers the scene for occupied rooms.
    """
    rooms = hass.states.entity_ids(domain_filter='room')
    for room in rooms:
        room = hass.states.get(room)
        if room.state != 'occupied':
            logger.debug('room not occupied %s %s', room, room.state)
            continue
        room_name = room.object_id

        toggle_name = 'input_boolean.room_{}'.format(room_name)
        toggle_input = hass.states.get(toggle_name)
        if toggle_input.state == 'off':
            logger.debug('room off %s', room)
            continue

        # use input_boolean dark sensors because they lag behind 15 mins
        sensor_name = 'input_boolean.dark_{}'.format(room_name)
        dark_sensor = hass.states.get(sensor_name)
        if dark_sensor.state == 'off':
            diff = dt_util.now() - dark_sensor.last_changed
            maxtime = datetime.timedelta(minutes=30)
            if diff <= maxtime:
                scene_name = 'scene.{}_not_occupied'.format(room_name)
                logger.info('turning on scene %s for room %s '
                            'due to dark sensor', scene_name, room_name)
                hass.services.call('scene', 'turn_on', {
                    'entity_id': scene_name,
                })
            logger.debug('room dark %s', room)
            continue

        scene_name = 'scene.{}_{}'.format(room_name, room.state)
        if scene_name not in hass.states.entity_ids('scene'):
            logger.debug('no scene configured with name %s', scene_name)
            return

        logger.info('turning on scene %s for room %s', scene_name, room_name)
        hass.services.call('scene', 'turn_on', {'entity_id': scene_name})


set_scene(hass, data, logger)
