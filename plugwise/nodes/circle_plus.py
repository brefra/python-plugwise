"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Circle+ node object
"""
import threading
from plugwise.constants import (
    NODE_TYPE_STICK,
    NODE_TYPE_CIRCLE_PLUS,
    NODE_TYPE_CIRCLE,
    NODE_TYPE_SWITCH,
    NODE_TYPE_SENSE,
    NODE_TYPE_SCAN,
    NODE_TYPE_STEALTH,
)
from plugwise.node import PlugwiseNode
from plugwise.nodes.circle import PlugwiseCircle
from plugwise.messages.requests import CircleScanRequest
from plugwise.messages.responses import CircleScanResponse


class PlugwiseCirclePlus(PlugwiseCircle):
    """provides interface to the Plugwise Circle+ nodes
    """
    def __init__(self, mac, stick, info_message):
        PlugwiseCircle.__init__(self, mac, stick, info_message)
        self._pulse_1s = None
        self._pulse_8s = None
        self._pulse_hour = None
        self._gain_a = None
        self._gain_b = None
        self._off_ruis = None
        self._off_tot = None
        self._plugwise_nodes = []
        self._scan_thread = threading.Timer(2, self._request_scan).start()
        self._request_calibration()

    def on_message(self, message):
        """
        Process received message
        """
        if isinstance(message, CircleScanResponse):
            self._process_scan_response(message)
            self.stick.message_processed(message.seq_id)
        else:
            self.stick.logger.debug(
                "Unsupported message type '%s' received for circle+ with mac %s",
                str(message.__class__.__name__),
                self.get_mac(),
            )
        self.stick.message_processed(message.seq_id)

    def _request_scan(self):
        """Query circle+ for registered nodes
        """
        self.stick.logger.debug("Query circle+ for known Plugwise nodes")
        for node_id in range(0, 63):
            self.stick.send(CircleScanRequest(self.mac, node_id))
        self.stick.send(
            CircleScanRequest(self.mac, node_id),
            self.stick.discovery_finished,
        )

    def _process_scan_response(self, message):
        """ Process scan response message """
        if message.node_mac.value != b'FFFFFFFFFFFFFFFF':
            self.stick.logger.debug("Linked pluswise node with mac %s found, discover node type", message.node_mac.value.decode("ascii"))
            self.stick.discover_node(message.node_mac.value.decode("ascii"))
