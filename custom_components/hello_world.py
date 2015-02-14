"""
custom_components.hello_world
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Implements the bare minimum that a component should implement.
"""

# The domain of your component. Should be equal to the name of your component
DOMAIN = "hello_world"

# List of component names (string) your component depends upon
DEPENDENCIES = []


def setup(hass, config):
    """ Setup our skeleton component. """

    # States are in the format DOMAIN.OBJECT_ID
    hass.states.set('hello_world.Hello_World', 'Works!')

    # return boolean to indicate that initialization was successful
    return True
