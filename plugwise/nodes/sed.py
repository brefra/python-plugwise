"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise SED (Sleeping Endpoint Device) base object
"""

from plugwise.constants import (
    SED_CLOCK_INTERVAL,
    SED_CLOCK_SYNC,
    SED_MAINTENANCE_INTERVAL,
    SED_SLEEP_FOR,
    SED_STAY_ACTIVE,
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
    """provides base class for SED based nodes like Scan, Sense & Switch"""

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self._SED_requests = {}
        self._maintenance_interval = SED_MAINTENANCE_INTERVAL
        self._new_maintenance_interval = None

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
            "Awake message type '%s' received from %s",
            str(message.awake_type.value),
            self.get_mac(),
        )
        # awake_type
        # 0 : SED available for maintenance
        # 1 : SED joins network for first time
        # 2 : SED joins again while it has already joined, e.g. after reinserting a battery
        # 3 : SED is awake to notify state change
        # 4 : <unknown>
        # 5 : SED is awake due to button press
        if (
            message.awake_type.value == 0
            or message.awake_type.value == 1
            or message.awake_type.value == 2
            or message.awake_type.value == 5
        ):
            for request in self._SED_requests:
                (request_message, callback) = self._SED_requests[request]
                self.stick.logger.info(
                    "Send queued %s message to SED node %s",
                    request_message.__class__.__name__,
                    self.get_mac(),
                )
                self.stick.send(request_message, callback)
            self._SED_requests = {}
        else:
            if message.awake_type.value == 3:
                self.stick.logger.debug(
                    "Node %s awake for state change", self.get_mac()
                )
            else:
                self.stick.logger.info(
                    "Unknown awake message type (%s) received for node %s",
                    str(message.awake_type.value),
                    self.get_mac(),
                )

    def _queue_request(self, request_message, callback=None):
        """Queue request to be sent when SED is awake. Last message wins """
        self._SED_requests[request_message.ID] = (
            request_message,
            callback,
        )

    def _request_info(self, callback=None):
        """ Request info from node"""
        self._queue_request(
            NodeInfoRequest(self.mac),
            callback,
        )

    def ping(self, callback=None):
        """ Ping node"""
        self._queue_request(
            NodePingRequest(self.mac),
            callback,
        )

    def _wake_up_interval_accepted(self):
        """ Callback after wake up interval is received and accepted by SED """
        self._wake_up_interval = self._new_maintenance_interval

    def Configure_SED(
        self,
        stay_active=SED_STAY_ACTIVE,
        sleep_for=SED_SLEEP_FOR,
        maintenance_interval=SED_MAINTENANCE_INTERVAL,
        clock_sync=SED_CLOCK_SYNC,
        clock_interval=SED_CLOCK_INTERVAL,
    ):
        """Reconfigure the sleep/awake settings for a SED send at next awake of SED"""
        message = NodeSleepConfigRequest(
            self.mac,
            stay_active,
            maintenance_interval,
            sleep_for,
            clock_sync,
            clock_interval,
        )
        self._queue_request(message, self._wake_up_interval_accepted)
        self._new_maintenance_interval = maintenance_interval
        self.stick.logger.info(
            "Queue %s message to be send at next awake of SED node %s",
            message.__class__.__name__,
            self.get_mac(),
        )
