"""
Templated scenes

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene.template/
"""
import logging
import os
import yaml
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.scene import Scene, STATES
from homeassistant.components.scene.homeassistant import _process_config
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ENTITIES, CONF_NAME, CONF_PLATFORM,
    CONF_STATE_TEMPLATE)
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.helpers.template import Template

PLATFORM = 'template'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): PLATFORM,
    vol.Required(STATES): vol.All(
        cv.ensure_list,
        [
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_STATE_TEMPLATE): cv.string,
            }
        ]
    ),
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up template scene entries."""
    scene_config = config.get(STATES)

    async_add_entities(
        TemplateScene(
            hass, scene.get(CONF_NAME), scene.get(CONF_STATE_TEMPLATE)
        ) for scene in scene_config
    )
    return True


class TemplateScene(Scene):
    """A template scene is a scene that is rendered each time it is activated."""

    def __init__(self, hass, name, template):
        """Initialize the scene."""
        self.hass = hass
        self._name = name
        self.template = Template(template, hass)

    @property
    def name(self):
        return self._name

    async def async_activate(self):
        """Activate scene. Try to get entities into requested state."""
        rendered = self.template.async_render()
        _LOGGER.info('Scene template "%s" rendered as:\n%s', self._name, rendered)
        entities = yaml.load(rendered, Loader=yaml.SafeLoader)
        if entities is None:
            _LOGGER.warning('Scene template "%s" contains no entities', self._name)
            return
        scene_config = _process_config({
            CONF_NAME: self.name,
            CONF_ENTITIES: entities,
        })
        await async_reproduce_state(
            self.hass, scene_config.states.values(), True)
