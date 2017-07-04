"""
Wrapper for setting the current home 'mode'
"""

hass.services.call('input_select', 'select_option', {
    'entity_id': 'input_select.myhome_mode',
    'option': data.get('mode').title(),
})
