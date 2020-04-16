"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Base for serial or socket connections
"""

class StickConnection(object):
    """
    Generic Plugwise stick connection
    """
    def __init__(self):
        """
        :return: None
        """

    def send(self, message, callback=None):
        """
        :return: None
        """
        raise NotImplementedError

    def stop_connection(self):
        """
        :return: None
        """
        raise NotImplementedError
