"""
custom_components.myhome
~~~~~~~~~~~~~~~~~~~~~~~~~

Custom rules/automation for my home
"""
import logging
import time

from functools import partial

import homeassistant.components as core
import homeassistant.components.mysensors as mysensors
import homeassistant.helpers.event as helper

from homeassistant.components.device_tracker import (
    ATTR_DEV_ID, ATTR_LOCATION_NAME, SERVICE_SEE)
from homeassistant.components.device_tracker import (
    DOMAIN as DOMAIN_DEVICE_TRACKER)

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.mysensors.device import (
    ATTR_NODE_ID, ATTR_CHILD_ID)

from homeassistant.const import (
    STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE)

from homeassistant.core import split_entity_id
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.service import (
    extract_entity_ids, call_from_config)

from homeassistant.util import (slugify, convert)

DOMAIN = 'myhome'
DEPENDENCIES = ['group', 'scene', 'input_select', 'mysensors']

_LOGGER = logging.getLogger(__name__)

# configuration
CONF_RFID = 'rfid'
CONF_TOUCH = 'touch'
CONF_RESPONSE = 'response'

# services
SERVICE_DIM = 'dim'
SERVICE_BRIGHTEN = 'brighten'
SERVICE_SET_TOUCH = 'set_touch'
SERVICE_SEND_MSG = 'send_msg'

# attributes
ATTR_BRIGHTNESS_STEP = 'brightness_step'
ATTR_COMMAND = 'command'
ATTR_VALUE_TYPE = 'value_type'
ATTR_SUB_TYPE = 'sub_type'
ATTR_ACK = 'ack'
ATTR_PAYLOAD = 'payload'


def service_send_message(hass, service):
    """Send an arbitrary message to a MySensors node"""
    from mysensors.mysensors import Message
    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if gateways is None:
        _LOGGER.warning("MySensors gateways config is unavailable")
        return
    entity_ids = extract_entity_ids(hass, service)
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        attr = state.attributes
        node_id = attr.get(ATTR_NODE_ID, 0)
        child_id = attr.get(ATTR_CHILD_ID, 0)
        value_type = service.data.get(ATTR_VALUE_TYPE, 0)
        sub_type = service.data.get(ATTR_SUB_TYPE, 0)
        ack = service.data.get(ATTR_ACK, 0)
        payload = service.data.get(ATTR_PAYLOAD, '')
        for _, gateway in gateways.items():
            msg = Message().modify(
                node_id=node_id,
                child_id=child_id,
                type=value_type,
                sub_type=sub_type,
                ack=ack,
                payload=payload,
            )
            gateway.fill_queue(msg.encode)


def register_presence_handlers(hass, config):
    """ Registers the event handlers that handle presence. """
    rfid_sensor = config[DOMAIN].get(CONF_RFID, None)
    if rfid_sensor is None:
        _LOGGER.warning('RFID sensor not configured.')
        return

    def rfid_seen(now=None):
        """ Calls see service periodically with state of RFID sensor. """
        rfid_state = hass.states.get(rfid_sensor)
        location = STATE_NOT_HOME
        if rfid_state is not None and str(rfid_state.state) == '1':
            location = STATE_HOME
        # _LOGGER.debug('rfid %s state is %s', rfid_sensor, location)
        hass.services.call(DOMAIN_DEVICE_TRACKER, SERVICE_SEE, {
            ATTR_DEV_ID: split_entity_id(rfid_sensor)[1],
            ATTR_LOCATION_NAME: location,
        })

    helper.track_utc_time_change(hass, rfid_seen, second=0)

    def rfid_state_change(entity_id, old_state, new_state):
        """ Calls see service immediately with state of RFID sensor. """
        rfid_seen()

    helper.track_state_change(hass, rfid_sensor, rfid_state_change)


def get_brightness(hass, service):
    """ Returns the brightness for a group. """
    # there's no brightness attribute for a group so just pick the first one
    # in the group and return that
    target_ids = extract_entity_ids(hass, service)
    target_id = target_ids[0]
    state = hass.states.get(target_id)
    return state.attributes.get(ATTR_BRIGHTNESS, 0)


def change_brightness(hass, service, bri):
    """ Actually brightens/dims a group. """
    target_ids = extract_entity_ids(hass, service)
    if bri <= 0:
        core.turn_off(hass, target_ids)
    elif bri <= 255:
        core.turn_on(hass, target_ids, brightness=bri)


def service_light_dim(hass, service):
    """ Dims lights by a step value. """
    bri = get_brightness(hass, service)
    bri -= convert(service.data.get(ATTR_BRIGHTNESS_STEP), int, 50)
    bri = max(0, bri)
    change_brightness(hass, service, bri)


def service_light_brighten(hass, service):
    """ Brightens lights by a step value. """
    bri = get_brightness(hass, service)
    bri += convert(service.data.get(ATTR_BRIGHTNESS_STEP), int, 50)
    bri = min(255, bri)
    change_brightness(hass, service, bri)


def register_touch_control_handlers(hass, config):
    """ Registers handlers for touch scene controllers. """
    hass.services.register(DOMAIN, SERVICE_DIM,
            partial(service_light_dim, hass))
    hass.services.register(DOMAIN, SERVICE_BRIGHTEN,
            partial(service_light_brighten, hass))

    controllers = config[DOMAIN].get(CONF_TOUCH, None)
    if controllers is None:
        _LOGGER.info('No touch controllers configured.')
        return

    def send_scene_response(node_id, child_id, value):
        """ Sends a response to a sensor. """
        gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
        if gateways is None:
            _LOGGER.warning("MySensors gateways config is unavailable")
            return
        for _, gateway in gateways.items():
            value_type = gateway.const.SetReq.V_SCENE_ON
            gateway.set_child_value(node_id, child_id, value_type, value)

    def set_touch_service(service):
        """ Service that sends a command to a touch controller. """
        entity_ids = extract_entity_ids(hass, service)
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            attr = state.attributes
            node_id = attr.get(ATTR_NODE_ID, None)
            child_id = attr.get(ATTR_CHILD_ID, None)
            cmd = service.data.get(ATTR_COMMAND, 0)
            send_scene_response(node_id, child_id, cmd)

    hass.services.register(DOMAIN, SERVICE_SET_TOUCH, set_touch_service)

    def controller_state_change(entity_id, old_state, new_state):
        """ Callback for touch controller state change. """
        if new_state.state == STATE_UNAVAILABLE:
            return
        try:
            state = int(new_state.state)
        except ValueError:
            _LOGGER.error("Invalid state %s", new_state.state)
            return
        attr = new_state.attributes
        controller = controllers[entity_id]
        action = controller.get(state, None)
        if action is not None:
            # remove response before call or config will not validate
            response = action.pop(CONF_RESPONSE, int(state))
            call_from_config(hass, action)
            if response is not None:
                node_id = attr.get(ATTR_NODE_ID, None)
                child_id = attr.get(ATTR_CHILD_ID, None)
                _LOGGER.debug("Sending response %s to %s.%s",
                              response, node_id, child_id)
                send_scene_response(node_id, child_id, response)
        elif state != 0:
            _LOGGER.warning('Action not found for state %s', state)
        # reset the touch controller state
        hass.states.set(entity_id, 0, attr)

    for controller in controllers:
        helper.track_state_change(hass, controller, controller_state_change)


def monkeypatch_serial_gateway(hass):
    """
    Monkey patch the send method to rate limit writes since
    my gateway fails even at low baud rates.
    """
    from mysensors.mysensors import SerialGateway
    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if gateways is None:
        _LOGGER.warning("MySensors gateways config is unavailable")
        return
    for _, gateway in gateways.items():
        if not isinstance(gateway, SerialGateway):
            continue
        _LOGGER.info("monkeypatching MySensors serial gateway")
        send = gateway.send
        def send_delay(*args, **kwargs):
            ret = send(*args, **kwargs)
            time.sleep(0.095)
            return ret
        gateway.send = send_delay


def setup(hass, config):
    """ Setup myhome component. """
    register_presence_handlers(hass, config)
    _LOGGER.info('registered presense handlers')

    hass.services.register(DOMAIN, SERVICE_SEND_MSG,
        partial(service_send_message, hass))
    monkeypatch_serial_gateway(hass)
    _LOGGER.info('monkey patched mysensors')

    register_touch_control_handlers(hass, config)
    _LOGGER.info('registered touch control handlers')

    return True
