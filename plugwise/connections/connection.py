"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Base for serial or socket connections
"""

class StickConnection(object):
    """ Generic Plugwise stick connection"""

    def open_port(self) -> bool:
        """Placeholder to initialize the connection"""
        raise NotImplementedError

    def is_connected(self):
        """Placeholder to get current state of connection"""
        raise NotImplementedError

    def read_thread_alive(self):
        """Placeholder to get current state of the reader thread"""
        raise NotImplementedError

    def write_thread_alive(self):
        """Placeholder to get current state of the writer thread"""
        raise NotImplementedError

    def send(self, message, callback=None):
        """Placeholder to send message"""
        raise NotImplementedError

    def close_port(self):
        """Placeholder to disconnect"""
        raise NotImplementedError
