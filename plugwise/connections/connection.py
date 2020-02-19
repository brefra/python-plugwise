"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Base for serial or socket connections
"""


class StickConnection(object):
    """
    Generic Plugwise stick connection
    """

    stick = None

    def set_stick(self, stick):
        """
        :return: None
        """
        self.stick = stick

    def send(self, message, callback=None):
        """
        :return: None
        """
        raise NotImplementedError
