"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Socket connection
"""
import time
import threading
import logging
from queue import Queue
import socket
from plugwise.constants import SLEEP_TIME
from plugwise.connections.connection import StickConnection
from plugwise.message import PlugwiseMessage
from plugwise.util import PlugwiseException


class SocketConnection(StickConnection):
    """
    Wrapper for Socket connection configuration
    """

    def __init__(self, device, stick=None):
        StickConnection.__init__(self)
        self.logger = logging.getLogger("plugwise")
        self._device = device
        self.stick = stick
        # get the address from a <host>:<port> format
        addr = device.split(":")
        addr = (addr[0], int(addr[1]))
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect(addr)
        except Exception:
            self.logger.error(
                "Could not open socket, \
                              no messages are read or written to the bus"
            )
            raise plugwiseException("Could not open socket port")
        # build a read thread
        self._listen_process = threading.Thread(
            None, self.read_daemon, "plugwise-process-reader", (), {}
        )
        self._listen_process.daemon = True
        self._listen_process.start()

        # build a writer thread
        self._write_queue = Queue()
        self._write_process = threading.Thread(
            None, self.write_daemon, "plugwise-connection-writer", (), {}
        )
        self._write_process.daemon = True
        self._write_process.start()

    def stop_connection(self):
        """Close the socket."""
        self.logger.warning("Stop executed")
        try:
            self._socket.close()
        except Exception:
            self.logger.error("Error while closing socket")
            raise plugwiseException("Error while closing socket")
        time.sleep(1)

    def feed_parser(self, data):
        """Parse received message."""
        assert isinstance(data, bytes)
        self.stick.feed_parser(data)

    def send(self, message, callback=None):
        """Add message to write queue."""
        assert isinstance(message, PlugwiseMessage)
        self._write_queue.put_nowait((message, callback))

    def read_daemon(self):
        """Read thread."""
        while True:
            data = self._socket.recv(9999)
            self.feed_parser(data)

    def write_daemon(self):
        """Write thread."""
        while True:
            (message, callback) = self._write_queue.get(block=True)
            self.logger.info("Sending message on USB bus: %s", str(message))
            self.logger.error("Sending binary message:  %s", str(message.serialize()))
            self._socket.send(message.serialize())
            time.sleep(SLEEP_TIME)
            if callback:
                callback()
