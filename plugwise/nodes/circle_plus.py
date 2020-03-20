"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Circle+ node object
"""
import threading
from datetime import datetime
from plugwise.constants import (
    MAX_TIME_DRIFT,
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
from plugwise.messages.requests import (
    CirclePlusRealTimeClockGetRequest,
    CirclePlusRealTimeClockSetRequest,
    CirclePlusScanRequest,
)
from plugwise.messages.responses import (
    CirclePlusRealTimeClockResponse,
    CircleScanResponse,
)

class PlugwiseCirclePlus(PlugwiseCircle):
    """provides interface to the Plugwise Circle+ nodes
    """

    def __init__(self, mac, address, stick):
        PlugwiseCircle.__init__(self, mac, address, stick)
        self._plugwise_nodes = []
        self._scan_for_nodes_callback = None
        self._print_progress = False
        self._realtime_clock_offset = None

    def _circle_plus_message(self, message):
        """
        Process received message
        """
        if isinstance(message, CirclePlusRealTimeClockResponse):
            self._response_realtime_clock(message)
        elif isinstance(message, CircleScanResponse):
            self._process_scan_response(message)
        else:
            self.stick.logger.waning(
                "Unsupported message type '%s' received from circle with mac %s",
                str(message.__class__.__name__),
                self.get_mac(),
            )
        self.stick.message_processed(message.seq_id)

    def scan_for_nodes(self, callback=None):
        self._scan_for_nodes_callback = callback
        for node_address in range(0, 64):
            self.stick.send(CirclePlusScanRequest(self.mac, node_address))

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
            self._scan_for_nodes_callback(self._plugwise_nodes)
            self._scan_for_nodes_callback = None


    def get_real_time_clock(self, callback=None):
        """ get current datetime of internal clock of CirclePlus """
        self.stick.send(
            CirclePlusRealTimeClockGetRequest(self.mac), callback,
        )

    def _response_realtime_clock(self, message):
        dt = datetime(
            message.date.value.year,
            message.date.value.month,
            message.date.value.day,
            message.time.value.hour,
            message.time.value.minute,
            message.time.value.second,
        )
        realtime_clock_offset = message.timestamp.replace(microsecond=0) - (dt + self.stick.timezone_delta)
        if realtime_clock_offset.days == -1:
            self._realtime_clock_offset = realtime_clock_offset.seconds - 86400
        else:
            self._realtime_clock_offset = realtime_clock_offset.seconds
        self.stick.logger.debug("Realtime clock has drifted " + str(self._realtime_clock_offset) + " sec")

    def set_real_time_clock(self, callback=None):
        """ set internal clock of CirclePlus """
        self.stick.send(
            CirclePlusRealTimeClockSetRequest(self.mac, datetime.utcnow()), callback,
        )

    def sync_real_time_clock(self, max_drift=MAX_TIME_DRIFT) -> bool:
        """ Sync real time clock of node if time has drifted more than max drifted
        """
        if self._real_time_clock_offset != None:
            if self._real_time_clock_offset > max_drift or self._real_time_clock_offset < max_drift:
                self.set_real_time_clock()
                return True
        return False
