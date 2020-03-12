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

    def __init__(self, mac, address, stick):
        PlugwiseCircle.__init__(self, mac, address, stick)
        self._plugwise_nodes = []
        self._scan_for_nodes_callback = None
        self._print_progress = False

    def scan_for_nodes(self, callback=None):
        self._scan_for_nodes_callback = callback
        for node_address in range(0, 64):
        #for node_address in range(0, 10):
            self.stick.send(CircleScanRequest(self.mac, node_address))

    def _process_scan_response(self, message):
        """ Process scan response message """
        self.stick.logger.debug(
            "Process scan response for address %s", message.node_address.value
        )
        if message.node_mac.value != b"FFFFFFFFFFFFFFFF":
            if self.stick.print_progress:
                print(
                    "Scan at address "
                    + str(message.node_address.value)
                    + " => node found with mac "
                    + message.node_mac.value.decode("ascii")
                )
            self.stick.logger.debug(
                "Linked plugwise node with mac %s found",
                message.node_mac.value.decode("ascii"),
            )
            self._plugwise_nodes.append(
                [message.node_mac.value.decode("ascii"), message.node_address.value]
            )
        else:
            if self.stick.print_progress:
                print(
                    "Scan at address "
                    + str(message.node_address.value)
                    + " => no node found"
                )
        if message.node_address.value == 63 and self._scan_for_nodes_callback != None:
        #if message.node_address.value == 9 and self._scan_for_nodes_callback != None:
            self._scan_for_nodes_callback(self._plugwise_nodes)
            self._scan_for_nodes_callback = None
