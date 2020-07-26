"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Serial connection
"""
import logging
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
        super().__init__(port, stick)
        self._baud = BAUD_RATE
        self._byte_size = BYTE_SIZE
        self._stopbits = STOPBITS
        self._parity = serial.PARITY_NONE

    def _open_connection(self):
        """Open serial port"""
        self.stick.logger.debug("Open serial port %s", self.port)
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self._baud,
                bytesize=self._byte_size,
                parity=self._parity,
                stopbits=self._stopbits,
                timeout=1,
            )
            self._serial.open()
        except serial.serialutil.SerialException as err:
            self.stick.logger.debug(
                "Failed to connect to serial port %s, %s", self._port, err,
            )
            raise PortError(err)
        else:
            self._is_connected = self._serial.isOpen()
            if self._is_connected:
                self._reader_start("serial_reader_deamon")
                self._writer_start("serial_writer_deamon")
                self.stick.logger.debug(
                    "Successfully connected to serial port %s", self.port
                )
            else:
                self.stick.logger.error(
                    "Failed to open serial port %s", self._port,
                )

    def _close_connection(self):
        """Close serial port."""
        try:
            self._reader_thread.close()
        except serial.serialutil.SerialException as err:
            self.stick.logger.debug(
                "Failed to close serial port %s, %s", self._port, err,
            )
            raise PortError(err)

    def _reader(self):
        """Read thread."""
        if self._is_connected:
            try:
                serial_data = self._serial.read_all()
            except serial.serialutil.SerialException as err:
                self.stick.logger.debug("Error while reading data from serial port : %s", err)
                self._is_connected = False
                raise PortError(err)
            else:
                return serial_data
        return None

    def _writer(self, data):
        """Write data to serial port"""
        try:
            self._reader_thread.write(data)
        except serial.serialutil.SerialException as err:
            self.stick.logger.debug("Error while writing data to serial port : %s", err)
            self._is_connected = False
            raise PortError(err)
