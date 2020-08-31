"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise SED (Sleeping Endpoint Device) base object
"""

from plugwise.constants import (
    SED_AWAKE_DURATION,
    SED_SLEEP_DURATION,
    SED_AWAKE_INTERVAL,
)
from plugwise.node import PlugwiseNode
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import NodeAwakeResponse
from plugwise.messages.requests import (
    NodeInfoRequest,
    NodePingRequest,
    NodeSleepConfigRequest,
)


class NodeSED(PlugwiseNode):
    """provides base class for SED based nodes like Scan, Sense & Switch 
    """

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self._SED_requests = {}

    def _on_message(self, message):
        """
        Process received message
        """
        if isinstance(message, NodeAwakeResponse):
            self._process_awake_response(message)
            self.stick.message_processed(message.seq_id)
        else:
            self._on_SED_message(message)

    def _on_SED_message(self, message):
        pass

    def _process_awake_response(self, message):
        """" Process awake message"""
        self.stick.logger.debug(
            "Awake message type %s received from %s",
            str(message.awake_type),
            self.get_mac(),
        )
        # awake_type
        # 0 : SED available for maintenance, so sent all queued maintenance requests
        # 1 : SED joins network for first time
        # 2 : SED joins again while it has already joined, e.g. after reinserting a battery
        # 3 : SED is awake to notify state change
        # 5 : SED is awake due to button press
        if (
            message.awake_type == 0
            or message.awake_type == 1
            or message.awake_type == 2
            or message.awake_type == 5
        ):
            for (request, callback) in self._maintenance_requests:
                self.stick.send(request, callback)
            self._maintenance_requests = []
        else:
            if message.awake_type != 3:
                self.stick.logger.info(
                    "Unknown awake message type received for node %s", self.get_mac()
                )

    def _send_request(self, request_message, callback=None):
        """Queue request to be sent when SED is awake. Last message wins """
        self._SED_requests[NodeInfoRequest.ID] = (
            request_message,
            callback,
        )

    def _request_info(self, callback=None):
        """ Request info from node"""
        self._send_request(
            NodeInfoRequest(self.mac), callback,
        )

    def ping(self, callback=None):
        """ Ping node"""
        self._send_request(
            NodePingRequest(self.mac), callback,
        )

    def Configure_SED(
        self,
        awake_duration=SCAN_AWAKE_DURATION,
        sleep_duration=SED_SLEEP_DURATION,
        wake_up_interval=SED_AWAKE_INTERVAL,
        callback=None,
    ):
        """Reconfigure the awake duration and interval settings at next awake of SED"""
        message = NodeSleepConfigRequest(
            self.mac, awake_duration, sleep_duration, wake_up_interval
        )
        self._send_request(message, callback)
