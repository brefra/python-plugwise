"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Socket connection
"""
import logging
import socket
from plugwise.constants import SLEEP_TIME
from plugwise.connections.connection import StickConnection
from plugwise.exceptions import PortError
from plugwise.message import PlugwiseMessage


class SocketConnection(StickConnection):
    """
    Wrapper for Socket connection configuration
    """

    def __init__(self, port, stick=None):
        super().__init__(port, stick)
        # get the address from a <host>:<port> format
        port_split = self.port.split(":")
        self._socket_host = port_split[0]
        self._socket_port = int(port_split[1])
        self._socket_address = (self._socket_host, self._socket_port)

    def _open_connection(self):
        """Open socket"""
        self.stick.logger.debug(
            "Open socket to host '%s' at port %s",
            self._socket_host,
            str(self._socket_port),
        )
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect(self._socket_address)
        except Exception as err:
            self.stick.logger.debug(
                "Failed to connect to host %s at port %s, %s",
                self._socket_host,
                str(self._socket_port),
                err,
            )
            raise PortError(err)
        else:
            self._reader_start("socket_reader_thread")
            self._writer_start("socket_writer_thread")
            self._is_connected = True
            self.stick.logger.debug(
                "Successfully connected to host '%s' at port %s",
                self._socket_host,
                str(self._socket_port),
            )

    def _close_connection(self):
        """Close the socket."""
        try:
            self._socket.close()
        except Exception as err:
            self.stick.logger.debug(
                "Failed to close socket to host %s at port %s, %s",
                self._socket_host,
                str(self._socket_port),
                err,
            )
            raise PortError(err)

    def _read_data(self):
        """Read data from socket."""
        if self._is_connected:
            try:
                socket_data = self._socket.recv(9999)
            except Exception as err:
                self.stick.logger.debug(
                    "Error while reading data from host %s at port %s : %s",
                    self._socket_host,
                    str(self._socket_port),
                    err,
                )
                self._is_connected = False
                raise PortError(err)
            else:
                return socket_data
        return None

    def _write_data(self, data):
        """Write data to socket"""
        try:
            self._socket.send(data)
        except Exception as err:
            self.stick.logger.debug("Error while writing data to socket port : %s", err)
            self._is_connected = False
            raise PortError(err)
