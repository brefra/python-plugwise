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
from plugwise.exceptions import PortError
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
        self.run_writer_thread = True
        self.run_reader_thread = True
        self._is_connected = False

    def open_port(self):
        """Open serial port"""
        self.stick.logger.debug("Open serial port")
        try:
            self.serial = serial.Serial(
                port = self.port,
                baudrate = self.baud,
                bytesize = self.bits,
                parity = self.parity,
                stopbits = self.stop,
            )
            self._reader_thread = serial.threaded.ReaderThread(self.serial, Protocol)
            self._reader_thread.start()
            self._reader_thread.protocol.parser = self.feed_parser
            self._reader_thread.connect()
        except serial.serialutil.SerialException as err:
            self.stick.logger.debug(
                "Failed to connect to port %s, %s",
                self.port,
                err,
            )
            raise PortError(err)
        else:
            self.stick.logger.debug("Successfully connected to serial port %s", self.port)
            self._write_queue = Queue()
            self._writer_thread = threading.Thread(None, self.writer_loop,
                                                "write_packets_process", (), {})
            self._writer_thread.daemon = True
            self._writer_thread.start()
            self.stick.logger.debug("Successfully connected to port %s", self.port)
            self._is_connected = True

    def close_port(self):
        """Close serial port."""
        self._is_connected = False
        self.run_writer_thread = False
        try:
            self._reader_thread.close()
        except serial.serialutil.SerialException:
            self.stick.logger.error("Error while closing device")
            raise PlugwiseException("Error while closing device")

    def read_thread_alive(self):
        """Return state of write thread"""
        return self._reader_thread.isAlive()

    def write_thread_alive(self):
        """Return state of write thread"""
        return self._writer_thread.isAlive()

    def is_connected(self):
        """Return connection state"""
        return self._is_connected

    def feed_parser(self, data):
        """Parse received message."""
        assert isinstance(data, bytes)
        self.stick.feed_parser(data)

    def send(self, message, callback=None):
        """Add message to write queue."""
        assert isinstance(message, PlugwiseMessage)
        self._write_queue.put_nowait((message, callback))

    def writer_loop(self):
        """Write thread."""
        while self.run_writer_thread:
            (message, callback) = self._write_queue.get(block=True)
            self.stick.logger.debug("Sending %s to plugwise stick (%s)", message.__class__.__name__, message.serialize())
            self._reader_thread.write(message.serialize())
            time.sleep(SLEEP_TIME)
            if callback:
                callback()