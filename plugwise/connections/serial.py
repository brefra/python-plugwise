"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Serial USB connection
"""
import time
import threading
import logging
from queue import Queue
import serial
import serial.threaded
from plugwise.constants import (
    BAUD_RATE,
    BYTE_SIZE,
    PARITY,
    SLEEP_TIME,
    STOPBITS,
)
from plugwise.connections.connection import StickConnection
from plugwise.message import PlugwiseMessage
from plugwise.util import PlugwiseException


class Protocol(serial.threaded.Protocol):
    """Serial protocol."""

    def data_received(self, data):
        # pylint: disable-msg=E1101
        self.parser(data)


class PlugwiseUSBConnection(StickConnection):
    """simple wrapper around serial module"""

    def __init__(self, port, stick=None):
        self.port = port
        self.baud = BAUD_RATE
        self.bits = BYTE_SIZE
        self.stop = STOPBITS
        self.parity = serial.PARITY_NONE
        self.stick = stick
        self.stick.logger.error("start serial port")
        try:
            self.serial = serial.Serial(
                port = self.port,
                baudrate = self.baud,
                bytesize = self.bits,
                parity = self.parity,
                stopbits = self.stop,
            )
        except serial.serialutil.SerialException:
            self.stick.logger.error(
                "Could not open serial port, no connection to the plugwise Zigbee network"
            )
            raise PlugwiseException("Could not open serial port")
        self._reader = serial.threaded.ReaderThread(self.serial, Protocol)
        self._reader.start()
        self._reader.protocol.parser = self.feed_parser
        self._reader.connect()
        self._write_queue = Queue()
        self._write_process = threading.Thread(None, self.write_daemon,
                                               "write_packets_process", (), {})
        self._write_process.daemon = True
        self._write_process.start()
        self.stick.logger.error("Serial port initialized")

    def stop(self):
        """Close serial port."""
        self.stick.logger.warning("Stop executed")
        try:
            self._reader.close()
        except serial.serialutil.SerialException:
            self.stick.logger.error("Error while closing device")
            raise PlugwiseException("Error while closing device")
        time.sleep(1)

    def feed_parser(self, data):
        """Parse received message."""
        #assert isinstance(data, bytes)
        self.stick.feed_parser(data)

    def write(self, data, callback=None):
        """Add message to write queue."""
        #assert isinstance(message, Message)
        self._write_queue.put_nowait((data, callback))

    def send(self, message, callback=None):
        """Add message to write queue."""
        assert isinstance(message, PlugwiseMessage)
        self._write_queue.put_nowait((message, callback))

    def write_daemon(self):
        """Write thread."""
        while True:
            (message, callback) = self._write_queue.get(block=True)
            self.stick.logger.error("Sending %s to plugwise stick (%s)", message.__class__.__name__, message.serialize())
            self._reader.write(message.serialize())
            time.sleep(SLEEP_TIME)
            if callback:
                callback()