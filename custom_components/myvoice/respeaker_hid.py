"""
ReSpeaker HID interface
"""
import asyncio
import logging
import threading
from respeaker.usb_hid.hidapi_backend import HidApiUSB
from .const import DOMAIN, ATTR_MODE, SERVICE_LEDS

_LOGGER = logging.getLogger(__name__)


def format_packet(data):
    """Returns a formatted string for the data packet"""
    address = ((data[1] << 8) & 0xFF) | data[0]
    length = ((data[3] << 8) & 0xFF) | data[2]
    hex = ' '.join('{:02X}'.format(x) for x in data[4:4 + length])
    return '[{:02X}:{}]: {}'.format(address, length, hex)


def write(hid, address, data):
    """Writes a register"""
    data = to_bytearray(data)
    length = len(data)
    packet = bytearray([address & 0xFF, (address >> 8) & 0xFF, length & 0xFF, (length >> 8) & 0xFF]) + data
    hid.write(packet)
    _LOGGER.debug('send: {}'.format(format_packet(packet)))


def read(hid, address, length):
    """Reads a register.  Currently only logs the result"""
    packet = bytearray([address & 0xFF, (address >> 8) & 0xFF | 0x80, length & 0xFF, (length >> 8) & 0xFF])
    hid.write(packet)
    _LOGGER.debug('send: {}'.format(format_packet(packet)))


def to_bytearray(data):
    if type(data) is int:
        array = bytearray([data & 0xFF])
    elif type(data) is bytearray:
        array = data
    elif type(data) is str:
        array = bytearray(data)
    elif type(data) is list:
        array = bytearray(data)
    else:
        raise TypeError('%s is not supported' % type(data))
    return array


def initialize_microphone(hid):
    """Initializes the microphone"""

    # increase the mic gain db from the default
    #write(hid, 0x10, [0x23])

    # turn all LEDs off
    write(hid, 0x0, [1, 0, 0, 0])


def setup(hass, config):
    """Sets up the HID interface for ReSpeaker"""
    devices = HidApiUSB.getAllConnectedInterface()
    hid = devices[0]

    initialize_microphone(hid)

    @asyncio.coroutine
    def recognize():
        write(hid, 0, [6, 0, 0, 0])
        for i in range(3, 16):
            write(hid, i, [255, 0, 0, 0])
            yield from asyncio.sleep(0.05)
            write(hid, i, [0, 0, 0, 0])

    modes = {
        'recognize': recognize,
    }

    @asyncio.coroutine
    def led_service(service):
        """Control the LEDs"""
        mode = service.data.get(ATTR_MODE)
        if mode in modes:
            yield from modes[mode]()

    hass.services.async_register(DOMAIN, SERVICE_LEDS, led_service)
    return True
