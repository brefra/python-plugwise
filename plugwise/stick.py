"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Main stick object to control associated plugwise plugs
"""
import logging
from datetime import datetime
import time
import threading
from datetime import datetime, timedelta
from plugwise.constants import (
    ACK_ERROR,
    ACK_TIMEOUT,
    MESSAGE_TIME_OUT,
    MESSAGE_RETRY,
    NODE_TYPE_STICK,
    NODE_TYPE_CIRCLE_PLUS,
    NODE_TYPE_CIRCLE,
    NODE_TYPE_SWITCH,
    NODE_TYPE_SENSE,
    NODE_TYPE_SCAN,
    NODE_TYPE_STEALTH,
    SLEEP_TIME,
)
from plugwise.connections.socket import SocketConnection
from plugwise.connections.serial import PlugwiseUSBConnection
from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CirclePlusScanRequest,
    CircleCalibrationRequest,
    CirclePlusRealTimeClockSetRequest,
    CirclePowerUsageRequest,
    CircleSwitchRequest,
    NodeInfoRequest,
    NodePingRequest,
    NodeRequest,
    StickInitRequest,
)
from plugwise.messages.responses import (
    CircleScanResponse,
    CircleCalibrationResponse,
    CirclePowerUsageResponse,
    CircleSwitchResponse,
    NodeInfoResponse,
    NodePingResponse,
    NodeResponse,
    StickInitResponse,
)
from plugwise.parser import PlugwiseParser
from plugwise.node import PlugwiseNode
from plugwise.nodes.circle import PlugwiseCircle
from plugwise.nodes.circle_plus import PlugwiseCirclePlus
from plugwise.util import inc_seq_id, validate_mac
from queue import Queue


class stick(object):
    """
    Plugwise connection stick
    """

    def __init__(self, port, callback=None):
        self.logger = logging.getLogger("plugwise")
        self._mac_stick = None
        self.network_online = False
        self.circle_plus_mac = None
        self.network_id = None
        self.parser = PlugwiseParser(self)
        self._plugwise_nodes = {}
        self._nodes_to_discover = []
        self.last_ack_seq_id = None
        self.expected_responses = {}
        self.print_progress = False
        self.timezone_delta = datetime.now() - datetime.utcnow()

        if ":" in port:
            self.logger.debug("Open socket connection to Plugwise Zigbee stick")
            self.connection = SocketConnection(port, self)
        else:
            self.logger.debug("Open USB serial connection to Plugwise Zigbee stick")
            self.connection = PlugwiseUSBConnection(port, self)
        self.logger.debug("Send init request to Plugwise Zigbee stick")
        # receive timeout deamon
        self._receive_timeout_thread = threading.Thread(
            None, self._receive_timeout_daemon, "receive_timeout_deamon", (), {}
        )
        self._receive_timeout_thread.daemon = True
        self._receive_timeout_thread.start()
        # send deamon
        self._send_message_queue = Queue()
        self._send_message_thread = threading.Thread(
            None, self._send_message_daemon, "send_messages_deamon", (), {}
        )
        self._send_message_thread.daemon = True
        self._send_message_thread.start()
        # update deamon
        self._auto_update_timer = None
        self._auto_update_first_run = True
        self._update_thread = threading.Thread(
            None, self._update_daemon, "update_daemon", (), {}
        )
        self._update_thread.daemon = True

        self.send(StickInitRequest(), callback)

    def nodes(self) -> list:
        """ Return mac addresses of known plugwise nodes """
        return list(self._plugwise_nodes.keys())

    def node(self, mac) -> PlugwiseNode:
        """ Return specific Plugwise node object"""
        assert isinstance(mac, str)
        if mac in self._plugwise_nodes:
            return self._plugwise_nodes[mac]
        return None

    def discover_node(self, mac, callback=None) -> bool:
        """ Discovery plugwise node """
        assert isinstance(mac, str)
        if validate_mac(mac) == True:
            self.send(
                NodeInfoRequest(bytes(mac, "ascii")), callback,
            )
            return True
        return False

    def scan(self, callback=None, print_progress=False):
        """ scan for connected plugwise nodes """

        def scan_finished(nodes_to_discover):
            """ Callback when scan is finished """
            time.sleep(1)
            self.logger.debug("Scan finished")
            self._nodes_discovered = 0
            self._nodes_to_discover = nodes_to_discover
            self._discovery_finished = False

            def node_discovered():
                self._nodes_discovered += 1
                if print_progress:
                    print(
                        "Discovered node "
                        + str(len(self._plugwise_nodes) - 1)
                        + " of "
                        + str(len(self._nodes_to_discover))
                    )
                self.logger.debug(
                    "Discovered Plugwise node %s of %s",
                    str(len(self._plugwise_nodes)),
                    str(self._nodes_to_discover),
                )
                if (len(self._plugwise_nodes) - 1) >= len(self._nodes_to_discover):
                    self._discovery_finished = True
                    self._nodes_to_discover = None
                    if callback != None:
                        callback()

            def timeout_expired():
                if not self._discovery_finished:
                    for (mac, address) in self._nodes_to_discover:
                        if mac not in self._plugwise_nodes.keys():
                            self.logger.warning(
                                "Failed to discover Plugwise node %s before timeout expired.",
                                str(mac),
                            )
                    if callback != None:
                        callback()

            # setup timeout for loading nodes
            discover_timeout = (
                30 + (len(nodes_to_discover) * 2) + (MESSAGE_TIME_OUT * MESSAGE_RETRY)
            )
            self.discover_timeout = threading.Timer(
                discover_timeout, timeout_expired
            ).start()
            if print_progress:
                print("Discovery of node types")
            for (mac, address) in nodes_to_discover:
                self.send(
                    NodeInfoRequest(bytes(mac, "ascii")), node_discovered,
                )

        if print_progress:
            self.print_progress = True
        if self.circle_plus_mac in self._plugwise_nodes:
            if self.print_progress:
                print("Scan Circle+ for connected nodes")
            self._plugwise_nodes[self.circle_plus_mac].scan_for_nodes(scan_finished)
        else:
            self.logger.warning("Plugwise stick not initialized yet.")

    def _append_node(self, mac, address, node_type):
        """ Add Plugwise node to be controlled """
        self.logger.debug(
            "Add new node type (%s) with mac %s", str(node_type), mac,
        )
        if node_type == NODE_TYPE_CIRCLE:
            self._plugwise_nodes[mac] = PlugwiseCircle(mac, address, self)
        elif node_type == NODE_TYPE_CIRCLE_PLUS:
            self._plugwise_nodes[mac] = PlugwiseCirclePlus(mac, address, self)
        else:
            self.logger.warning("Unsupported node type '%s'", str(node_type))

    def _remove_node(self, mac):
        """
        remove circle from stick

        :return: None
        """
        if mac in self._plugwise_nodes:
            del self._plugwise_nodes[mac]

    def feed_parser(self, data):
        """ Feed parser with new data """
        assert isinstance(data, bytes)
        self.parser.feed(data)

    def send(self, request, callback=None, retry_counter=0):
        """
        Submit request message into Plugwise Zigbee network and queue expected response
        """
        assert isinstance(request, NodeRequest)
        if isinstance(request, CirclePowerUsageRequest):
            response_message = CirclePowerUsageResponse()
        elif isinstance(request, NodeInfoRequest):
            response_message = NodeInfoResponse()
        elif isinstance(request, NodePingRequest):
            response_message = NodePingResponse()
        elif isinstance(request, CircleSwitchRequest):
            response_message = CircleSwitchResponse()
        elif isinstance(request, CircleCalibrationRequest):
            response_message = CircleCalibrationResponse()
        elif isinstance(request, CirclePlusScanRequest):
            response_message = CircleScanResponse()
        elif isinstance(request, StickInitRequest):
            response_message = StickInitResponse()
        else:
            response_message = None
        self._send_message_queue.put(
            [response_message, request, callback, retry_counter, None,]
        )

    def _send_message_daemon(self):
        while True:
            request_set = self._send_message_queue.get(block=True)
            if self.last_ack_seq_id != None:
                # Calc new seq_id based last received ack messsage
                seq_id = inc_seq_id(self.last_ack_seq_id)
            else:
                # first message, so use a fake seq_id
                seq_id = b"0000"
            self.expected_responses[seq_id] = request_set
            if not isinstance(request_set[1], StickInitRequest):
                mac = request_set[1].mac.decode("ascii")
                self.logger.debug(
                    "send %s to %s using seq_id %s",
                    request_set[1].__class__.__name__,
                    mac,
                    str(seq_id),
                )
                if mac in self._plugwise_nodes:
                    self._plugwise_nodes[mac].last_request = datetime.now()
                if self.expected_responses[seq_id][3] > 0:
                    self.logger.debug(
                        "Retry %s for message %s to %s",
                        str(self.expected_responses[seq_id][3]),
                        str(self.expected_responses[seq_id][1].__class__.__name__),
                        self.expected_responses[seq_id][1].mac.decode("ascii"),
                    )
            self.expected_responses[seq_id][4] = datetime.now()
            self.connection.send(request_set[1])
            time.sleep(SLEEP_TIME)
            timeout_counter = 0
            # Wait max 1 second for acknowledge response
            while (
                self.last_ack_seq_id != seq_id
                and timeout_counter <= 10
                and seq_id != b"0000"
                and self.last_ack_seq_id != None
            ):
                time.sleep(0.1)
                timeout_counter += 1
            if timeout_counter > 10:
                if seq_id in self.expected_responses:
                    if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                        self.logger.debug(
                            "Resend %s for %s (%s) because stick did not acknowledged send request",
                            str(self.expected_responses[seq_id][1].__class__.__name__),
                            self.expected_responses[seq_id][1].mac.decode("ascii"),
                            str(seq_id),
                        )
                        self.send(
                            self.expected_responses[seq_id][1],
                            self.expected_responses[seq_id][2],
                            self.expected_responses[seq_id][3] + 1,
                        )
                    else:
                        self.logger.warning(
                            "Drop %s request for mac %s because max (%s) retries reached",
                            self.expected_responses[seq_id][1].__class__.__name__,
                            self.expected_responses[seq_id][1].mac.decode("ascii"),
                            str(MESSAGE_RETRY),
                        )
                    del self.expected_responses[seq_id]

    def _receive_timeout_daemon(self):
        while True:
            for seq_id in list(self.expected_responses.keys()):
                if self.expected_responses[seq_id][4] != None:
                    if self.expected_responses[seq_id][4] < (
                        datetime.now() - timedelta(seconds=MESSAGE_TIME_OUT)
                    ):
                        self.logger.debug(
                            "Timeout expired for message with sequence ID %s",
                            str(seq_id),
                        )
                        if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                            self.logger.debug(
                                "Resend request %s",
                                str(
                                    self.expected_responses[seq_id][
                                        1
                                    ].__class__.__name__
                                ),
                            )
                            self.send(
                                self.expected_responses[seq_id][1],
                                self.expected_responses[seq_id][2],
                                self.expected_responses[seq_id][3] + 1,
                            )
                        else:
                            self.logger.warning(
                                "Drop %s request for mac %s because max (%s) retries reached",
                                self.expected_responses[seq_id][1].__class__.__name__,
                                self.expected_responses[seq_id][1].mac.decode("ascii"),
                                str(MESSAGE_RETRY),
                            )
                        del self.expected_responses[seq_id]
            time.sleep(MESSAGE_TIME_OUT)

    def new_message(self, message):
        """ Received message from Plugwise Zigbee network """
        assert isinstance(message, NodeResponse)
        self.logger.debug(
            "New %s message with seq id %s for %s",
            message.__class__.__name__,
            str(message.seq_id),
            message.mac.decode("ascii"),
        )
        mac = message.mac.decode("ascii")
        if isinstance(message, StickInitResponse):
            self._mac_stick = message.mac
            if message.network_is_online.value == 1:
                self.network_online = True
            else:
                self.network_online = False
            # Replace first 2 charactors by 00 for mac of circle+ node
            self.circle_plus_mac = "00" + message.circle_plus_mac.value[2:].decode(
                "ascii"
            )
            self.network_id = message.network_id.value
            # The first StickInitResponse gives the actual sequence ID
            if b"0000" in self.expected_responses:
                seq_id = b"0000"
            else:
                seq_id = message.seq_id
            # Discover Circle+, and "move" callback to discovery request
            if self.expected_responses[seq_id][2] != None:
                self.discover_node(
                    self.circle_plus_mac, self.expected_responses[seq_id][2]
                )
            else:
                self.discover_node(self.circle_plus_mac)
            del self.expected_responses[seq_id]
        elif isinstance(message, NodeInfoResponse):
            if not mac in self._plugwise_nodes:
                if message.node_type.value == NODE_TYPE_CIRCLE_PLUS:
                    self._append_node(mac, 0, message.node_type.value)
                else:
                    for (mac_to_discover, address) in self._nodes_to_discover:
                        if mac == mac_to_discover:
                            self._append_node(mac, address, message.node_type.value)
            self._plugwise_nodes[mac].on_message(message)
        else:
            if mac in self._plugwise_nodes:
                self._plugwise_nodes[mac].on_message(message)

    def message_processed(self, seq_id, ack_response=None):
        if seq_id in self.expected_responses:
            # excute callback at response of message
            self.logger.debug(
                "%s request with seq id %s processed",
                self.expected_responses[seq_id][0].__class__.__name__,
                str(seq_id),
            )
            if ack_response == ACK_TIMEOUT:
                if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                    self.logger.debug(
                        "Network time out received for (%s of %s) of %s to %s, resend request",
                        str(self.expected_responses[seq_id][3] + 1),
                        str(MESSAGE_RETRY + 1),
                        str(self.expected_responses[seq_id][1].__class__.__name__),
                        self.expected_responses[seq_id][1].mac.decode("ascii"),
                    )
                    if not isinstance(
                        self.expected_responses[seq_id][1], StickInitRequest
                    ):
                        mac = self.expected_responses[seq_id][1].mac.decode("ascii")
                        if mac in self._plugwise_nodes:
                            if self._plugwise_nodes[mac].get_available():
                                self.send(
                                    self.expected_responses[seq_id][1],
                                    self.expected_responses[seq_id][2],
                                    self.expected_responses[seq_id][3] + 1,
                                )
                else:
                    self.logger.debug(
                        "Max (%s) network time out messages received for %s to %s, drop request",
                        str(self.expected_responses[seq_id][3] + 1),
                        str(self.expected_responses[seq_id][1].__class__.__name__),
                        self.expected_responses[seq_id][1].mac.decode("ascii"),
                    )
                    # Mark node as unavailable
                    if not isinstance(
                        self.expected_responses[seq_id][1], StickInitRequest
                    ):
                        mac = self.expected_responses[seq_id][1].mac.decode("ascii")
                        if mac in self._plugwise_nodes:
                            if self._plugwise_nodes[mac].get_available():
                                self.logger.warning(
                                    "Mark %s as unavailabe because %s time out responses reached",
                                    mac,
                                    str(MESSAGE_RETRY + 1),
                                )
                                self._plugwise_nodes[mac].set_available(False)
            elif ack_response == None:
                if self.expected_responses[seq_id][2] != None:
                    try:
                        self.expected_responses[seq_id][2]()
                    except Exception as e:
                        self.logger.error(
                            "Error while executing callback after processing message : %s",
                            e,
                        )
            del self.expected_responses[seq_id]

    def stop(self):
        """
        Stop connection to Plugwise Zigbee network
        """

    def _update_daemon(self):
        """
        When node has not received any message during
        last 2 update polls, reset availability
        """
        while self._auto_update_timer != None:
            for mac in self._plugwise_nodes:
                # Do ping request
                self.logger.debug(
                    "Send ping to node %s",
                    mac,
                )
                self._plugwise_nodes[mac].ping()
                # Only power use updates for supported nodes
                if isinstance(self._plugwise_nodes[mac], PlugwiseCircle) or isinstance(
                    self._plugwise_nodes[mac], PlugwiseCirclePlus
                ):
                    # Don't check at first time
                    self.logger.debug("Request current power usage for node %s", mac)
                    if (
                        self._auto_update_first_run == False
                        and self._auto_update_timer != None
                    ):
                        # Only request update if node is available
                        if self._plugwise_nodes[mac].get_available():
                            self.logger.debug(
                                "Node '%s' is available for update request, last update (%s)",
                                mac,
                                str(self._plugwise_nodes[mac].get_last_update()),
                            )
                            # Skip update request if there is still an request expected to be received
                            open_requests_found = False
                            for seq_id in list(self.expected_responses.keys()):
                                if isinstance(
                                    self.expected_responses[seq_id][1],
                                    CirclePowerUsageRequest,
                                ):
                                    if mac == self.expected_responses[seq_id][
                                        1
                                    ].mac.decode("ascii"):
                                        open_requests_found = True
                                        break
                            if not open_requests_found:
                                self._plugwise_nodes[mac].update_power_usage()
                    else:
                        if self._auto_update_timer != None:
                            self.logger.debug(
                                "First request for current power usage for node %s", mac
                            )
                            self._plugwise_nodes[mac].update_power_usage()
            self._auto_update_first_run = False
            time.sleep(self._auto_update_timer)

    def auto_update(self, timer=None):
        """
        setup auto update polling for power usage.

        :return: bool
        """
        if timer == None:
            # Timer based on number of nodes and 3 seconds per node
            timer = len(self._plugwise_nodes) * 3
        if timer > 5:
            if self._auto_update_timer != None:
                self._auto_update_timer = timer
                self._update_thread.start()
            else:
                self._auto_update_first_run = True
                self._auto_update_timer = timer
                self._update_thread.start()
            return True
        elif timer == 0:
            self._auto_update_timer = None
            return False
        return False
