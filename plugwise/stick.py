"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Main stick object to control associated plugwise plugs
"""
import logging
import time
import serial
import sys
import threading
from datetime import datetime, timedelta
from plugwise.constants import (
    ACCEPT_JOIN_REQUESTS,
    ACK_ERROR,
    ACK_TIMEOUT,
    CB_JOIN_REQUEST,
    CB_NEW_NODE,
    MAX_TIME_DRIFT,
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
    WATCHDOG_DEAMON,
)
from plugwise.connections.socket import SocketConnection
from plugwise.connections.serial import PlugwiseUSBConnection
from plugwise.exceptions import (
    CirclePlusError,
    NetworkDown,
    PortError,
    StickInitError,
    TimeoutException,
)
from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CirclePlusScanRequest,
    CircleCalibrationRequest,
    CirclePlusRealTimeClockGetRequest,
    CirclePlusRealTimeClockSetRequest,
    CirclePowerUsageRequest,
    CircleSwitchRequest,
    NodeJoinAcceptRequest,
    NodeClockGetRequest,
    NodeClockSetRequest,
    NodeInfoRequest,
    NodePingRequest,
    NodeRequest,
    StickInitRequest,
)
from plugwise.messages.responses import (
    CirclePlusScanResponse,
    CircleCalibrationResponse,
    CirclePlusRealTimeClockResponse,
    CirclePowerUsageResponse,
    CircleSwitchResponse,
    NodeJoinAvailableResponse,
    SEDAwakeResponse,
    NodeClockResponse,
    NodeInfoResponse,
    NodePingResponse,
    NodeResponse,
    StickInitResponse,
)
from plugwise.parser import PlugwiseParser
from plugwise.node import PlugwiseNode
from plugwise.nodes.circle import PlugwiseCircle
from plugwise.nodes.circle_plus import PlugwiseCirclePlus
from plugwise.nodes.scan import PlugwiseScan
from plugwise.nodes.stealth import PlugwiseStealth
from plugwise.util import inc_seq_id, validate_mac
from queue import Queue


class stick(object):
    """
    Plugwise connection stick
    """

    def __init__(self, port, callback=None, print_progress=False):
        self.logger = logging.getLogger("python-plugwise")
        self._mac_stick = None
        self.port = port
        self.network_online = False
        self.circle_plus_mac = None
        self._circle_plus_discovered = False
        self._circle_plus_retries = 0
        self.network_id = None
        self.parser = PlugwiseParser(self)
        self._plugwise_nodes = {}
        self._nodes_registered = 0
        self._nodes_to_discover = {}
        self._nodes_not_discovered = {}
        self._accept_join_requests = ACCEPT_JOIN_REQUESTS
        self._stick_initialized = False
        self._stick_callbacks = {}
        self.last_ack_seq_id = None
        self.expected_responses = {}
        self.print_progress = print_progress
        self.timezone_delta = datetime.now().replace(
            minute=0, second=0, microsecond=0
        ) - datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        self._run_receive_timeout_thread = False
        self._run_send_message_thread = False
        self._run_update_thread = False

        if callback:
            self.auto_initialize(callback)

    def auto_initialize(self, callback=None):
        """ automatic initialization """

        def init_finished():
            if not self.network_online:
                self.logger.Error("plugwise Zigbee network down")
            else:
                if self.print_progress:
                    print("Scan Plugwise network")
                self.scan(callback)

        try:
            if self.print_progress:
                print("Open port")
            self.connect()
            if self.print_progress:
                print("Initialize Plugwise USBstick")
            self.initialize_stick(init_finished)
        except PortError as e:
            self.logger.error("Failed to connect: '%s'", e)
        except StickInitError as e:
            self.logger.error("Failed to initialize USBstick: '%s'", e)
        except NetworkDown as e:
            self.logger.error("Failed to communicated: Plugwise Zigbee network")
        except TimeoutException as e:
            self.logger.error("Timeout exception while initializing USBstick")
        except Exception as e:
            self.logger.error("Unknown error : %s", e)

    def connect(self, callback=None):
        """ Connect to stick and raise error if it fails"""
        self.init_callback = callback
        # Open connection to USB Stick
        if ":" in self.port:
            self.logger.debug("Open socket connection to Plugwise Zigbee stick")
            self.connection = SocketConnection(self.port, self)
        else:
            self.logger.debug("Open USB serial connection to Plugwise Zigbee stick")
            self.connection = PlugwiseUSBConnection(self.port, self)
        self.connection.connect()

        self.logger.debug("Starting threads...")
        # receive timeout deamon
        self._run_receive_timeout_thread = True
        self._receive_timeout_thread = threading.Thread(
            None, self._receive_timeout_loop, "receive_timeout_thread", (), {}
        )
        self._receive_timeout_thread.daemon = True
        self._receive_timeout_thread.start()
        # send deamon
        self._send_message_queue = Queue()
        self._run_send_message_thread = True
        self._send_message_thread = threading.Thread(
            None, self._send_message_loop, "send_messages_thread", (), {}
        )
        self._send_message_thread.daemon = True
        self._send_message_thread.start()
        # update deamon
        self._run_update_thread = False
        self._auto_update_timer = None
        self._update_thread = threading.Thread(
            None, self._update_loop, "update_thread", (), {}
        )
        self._update_thread.daemon = True
        self.logger.debug("All threads started")

    def initialize_stick(self, callback=None, timeout=MESSAGE_TIME_OUT):
        # Initialize USBstick
        if not self.connection.is_connected():
            raise StickInitError

        def cb_stick_initialized():
            """ Callback when initialization of Plugwise USBstick is finished """
            self._stick_initialized = True

            # Start watchdog deamon
            self._run_watchdog = True
            self._watchdog_thread = threading.Thread(
                None, self._watchdog_loop, "watchdog_thread", (), {}
            )
            self._watchdog_thread.daemon = True
            self._watchdog_thread.start()

            # Try to discover Circle+
            if self.circle_plus_mac:
                self.discover_node(self.circle_plus_mac)
            if callback:
                callback()

        self.logger.debug("Send init request to Plugwise Zigbee stick")
        self.send(StickInitRequest(), cb_stick_initialized)
        time_counter = 0
        while not self._stick_initialized and (time_counter < timeout):
            time_counter += 0.1
            time.sleep(0.1)
        if not self._stick_initialized:
            raise StickInitError
        if not self.network_online:
            raise NetworkDown

    def initialize_circle_plus(self, callback=None, timeout=MESSAGE_TIME_OUT):
        # Initialize Circle+
        if (
            not self.connection.is_connected()
            or not self._stick_initialized
            or not self.circle_plus_mac
        ):
            raise StickInitError
        # discover circle+ node
        self.discover_node(self.circle_plus_mac)

        time_counter = 0
        while not self._circle_plus_discovered and (time_counter < timeout):
            time_counter += 0.1
            time.sleep(0.1)
        if not self._circle_plus_discovered:
            raise CirclePlusError

    def disconnect(self):
        """ Disconnect from stick and raise error if it fails"""
        self._run_watchdog = False
        self._run_update_thread = False
        self._auto_update_timer = None
        self._run_send_message_thread = False
        self._run_receive_timeout_thread = False
        self.connection.disconnect()

    def subscribe_stick_callback(self, callback, callback_type):
        """ Subscribe callback to execute """
        if callback_type not in self._stick_callbacks:
            self._stick_callbacks[callback_type] = []
        self._stick_callbacks[callback_type].append(callback)

    def unsubscribe_stick_callback(self, callback, callback_type):
        """ Register callback to execute """
        if callback_type in self._stick_callbacks:
            self._stick_callbacks[callback_type].remove(callback)

    def do_callback(self, callback_type, callback_arg=None):
        """ Execute callbacks registered for specified callback type """
        if callback_type in self._stick_callbacks:
            for callback in self._stick_callbacks[callback_type]:
                try:
                    if callback_arg is None:
                        callback()
                    else:
                        callback(callback_arg)
                except Exception as e:
                    self.logger.error("Error while executing callback : %s", e)

    def _discover_after_scan(self):
        """ Helper to do callback for new node """
        node_discovered = None
        for mac in self._nodes_not_discovered.keys():
            if self._plugwise_nodes.get(mac, None):
                node_discovered = mac
                break
        if node_discovered:
            del self._nodes_not_discovered[node_discovered]
            self.do_callback(CB_NEW_NODE, node_discovered)

    def registered_nodes(self) -> int:
        """ Return number of nodes registered in Circle+ """
        # Include Circle+ too
        return self._nodes_registered + 1

    def nodes(self) -> list:
        """ Return list of mac addresses of discovered and supported plugwise nodes """
        return list(dict(filter(lambda item: item[1] is not None, self._plugwise_nodes.items())).keys())

    def node(self, mac : str) -> PlugwiseNode:
        """ Return specific Plugwise node object"""
        return self._plugwise_nodes.get(mac, None)

    def discover_node(self, mac: str, callback=None) -> bool:
        """ Discovery of plugwise node """
        if validate_mac(mac) == True:
            if mac not in self._plugwise_nodes.keys():
                if mac not in self._nodes_not_discovered.keys():
                    self._nodes_not_discovered[mac] = (
                        None,
                        None,
                    )
                self.send(
                    NodeInfoRequest(bytes(mac, "ascii")), callback,
                )
                return True
            else:
                return False
        else:
            return False

    def scan(self, callback=None):
        """ scan for connected plugwise nodes """

        def scan_finished(nodes_to_discover):
            """ Callback when scan is finished """
            time.sleep(1)
            self.logger.debug("Scan plugwise network finished")
            self._nodes_discovered = 0
            self._nodes_to_discover = nodes_to_discover
            self._nodes_registered = len(nodes_to_discover)
            self._discovery_finished = False

            def node_discovered():
                self._nodes_discovered += 1
                self.logger.debug(
                    "Discovered Plugwise node %s of %s",
                    str(len(self._plugwise_nodes)),
                    str(len(self._nodes_to_discover)),
                )
                if (len(self._plugwise_nodes) - 1) >= len(self._nodes_to_discover):
                    self._discovery_finished = True
                    self._nodes_to_discover = {}
                    self._nodes_not_discovered = {}
                    if callback:
                        callback()

            def timeout_expired():
                if not self._discovery_finished:
                    for mac in self._nodes_to_discover:
                        if mac not in self._plugwise_nodes.keys():
                            self.logger.warning(
                                "Failed to discover registered Plugwise node with MAC '%s' before timeout expired.",
                                str(mac),
                            )
                        else:
                            if mac in self._nodes_not_discovered:
                                del self._nodes_not_discovered[mac]
                    if callback:
                        callback()

            # setup timeout for loading nodes
            discover_timeout = (
                10 + (len(nodes_to_discover) * 2) + (MESSAGE_TIME_OUT * MESSAGE_RETRY)
            )
            self.discover_timeout = threading.Timer(
                discover_timeout, timeout_expired
            ).start()
            self.logger.debug("Start discovery of linked node types...")
            for mac in nodes_to_discover:
                self.discover_node(mac, node_discovered)

        def scan_circle_plus():
            """Callback when Circle+ is discovered"""
            if self._plugwise_nodes.get(self.circle_plus_mac):
                if self.print_progress:
                    print("Scan Circle+ for linked nodes")
                self.logger.debug("Scan Circle+ for linked nodes...")
                self._plugwise_nodes[self.circle_plus_mac].scan_for_nodes(scan_finished)
            else:
                self.logger.error(
                    "Circle+ is not discovered in %s", self._plugwise_nodes
                )

        # Discover Circle+
        if self.circle_plus_mac:
            if self._plugwise_nodes.get(self.circle_plus_mac):
                scan_circle_plus()
            else:
                if self.print_progress:
                    print("Discover Circle+")
                self.logger.debug("Discover Circle+ at %s", self.circle_plus_mac)
                self.discover_node(self.circle_plus_mac, scan_circle_plus)
        else:
            self.logger.error(
                "Plugwise stick not properly initialized, Circle+ MAC is missing."
            )

    def _append_node(self, mac, address, node_type):
        """ Add Plugwise node to be controlled """
        self.logger.debug(
            "Add new node type (%s) with mac %s", str(node_type), mac,
        )
        if node_type == NODE_TYPE_CIRCLE:
            if self.print_progress:
                print("Circle node found using mac " + mac)
            self._plugwise_nodes[mac] = PlugwiseCircle(mac, address, self)
        elif node_type == NODE_TYPE_CIRCLE_PLUS:
            if self.print_progress:
                print("Circle+ node found using mac " + mac)
            self._plugwise_nodes[mac] = PlugwiseCirclePlus(mac, address, self)
        elif node_type == NODE_TYPE_STEALTH:
            if self.print_progress:
                print("Stealth node found using mac " + mac)
            self._plugwise_nodes[mac] = PlugwiseStealth(mac, address, self)
        elif node_type == NODE_TYPE_SCAN:
            if self.print_progress:
                print("Scan node found using mac " + mac)
            self._plugwise_nodes[mac] = PlugwiseScan(mac, address, self)
        else:
            self.logger.warning("Unsupported node type '%s'", str(node_type))
            self._plugwise_nodes[mac] = None

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
            response_message = CirclePlusScanResponse()
        elif isinstance(request, CirclePlusRealTimeClockGetRequest):
            response_message = CirclePlusRealTimeClockResponse()
        elif isinstance(request, NodeClockGetRequest):
            response_message = NodeClockResponse()
        elif isinstance(request, StickInitRequest):
            response_message = StickInitResponse()
        else:
            response_message = None
        self._send_message_queue.put(
            [response_message, request, callback, retry_counter, None,]
        )

    def _send_message_loop(self):
        """ deamon to send messages in queue """
        while self._run_send_message_thread:
            request_set = self._send_message_queue.get(block=True)
            if self.last_ack_seq_id:
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
                if self._plugwise_nodes.get(mac):
                    self._plugwise_nodes[mac].last_request = datetime.now()
                if self.expected_responses[seq_id][3] > 0:
                    self.logger.debug(
                        "Retry %s for message %s to %s",
                        str(self.expected_responses[seq_id][3]),
                        str(self.expected_responses[seq_id][1].__class__.__name__),
                        self.expected_responses[seq_id][1].mac.decode("ascii"),
                    )
            else:
                self.logger.debug(
                    "send StickInitRequest using seq_id %s", str(seq_id),
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
            if timeout_counter > 10 and self._run_send_message_thread:
                if seq_id in self.expected_responses:
                    if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                        self.logger.info(
                            "Resend %s for %s because stick did not acknowledge request (%s)",
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
                        self.logger.info(
                            "Drop %s request for mac %s because max (%s) retries reached",
                            self.expected_responses[seq_id][1].__class__.__name__,
                            self.expected_responses[seq_id][1].mac.decode("ascii"),
                            str(MESSAGE_RETRY),
                        )
                    del self.expected_responses[seq_id]

    def _receive_timeout_loop(self):
        """ deamon to time out receive messages """
        while self._run_receive_timeout_thread:
            for seq_id in list(self.expected_responses.keys()):
                if isinstance(self.expected_responses[seq_id][1], StickInitRequest):
                    if self._cb_stick_initialized:
                        self._cb_stick_initialized()
                    del self.expected_responses[seq_id]
                elif isinstance(
                    self.expected_responses[seq_id][1], NodeClockSetRequest
                ):
                    del self.expected_responses[seq_id]
                elif isinstance(
                    self.expected_responses[seq_id][1],
                    CirclePlusRealTimeClockSetRequest,
                ):
                    del self.expected_responses[seq_id]
                else:
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
                                self.logger.info(
                                    "Drop %s request for mac %s because max (%s) retries reached",
                                    self.expected_responses[seq_id][
                                        1
                                    ].__class__.__name__,
                                    self.expected_responses[seq_id][1].mac.decode(
                                        "ascii"
                                    ),
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
            self.message_processed(seq_id)
        elif isinstance(message, NodeInfoResponse):
            if not mac in self._plugwise_nodes:
                if message.node_type.value == NODE_TYPE_CIRCLE_PLUS:
                    self._circle_plus_discovered = True
                    self._append_node(mac, 0, message.node_type.value)
                    if mac in self._nodes_not_discovered:
                        del self._nodes_not_discovered[mac]
                else:
                    for mac_to_discover in self._nodes_to_discover:
                        if mac == mac_to_discover:
                            self._append_node(mac, self._nodes_to_discover[mac_to_discover], message.node_type.value)
            if self._plugwise_nodes.get(mac):
                self._plugwise_nodes[mac].on_message(message)
        elif isinstance(message, SEDAwakeResponse):
            if self._plugwise_nodes.get(mac):
                self._plugwise_nodes[mac].on_message(message)
            else:
                self.logger.debug(
                    "Received awake message from unknown node with mac %s, discover node now",
                    mac,
                )
                self.discover_node(mac)
                self.message_processed(seq_id)
        elif isinstance(message, NodeJoinAvailableResponse):
            # New node that is not part of a plugwise network yet and wants to join
            if not self._plugwise_nodes.get(mac):
                if self._accept_join_requests:
                    # Send accept join request
                    self.send(NodeJoinAcceptRequest(mac, True))
                    # TODO: Circle+ registration ??
                else:
                    self.do_callback(CB_JOIN_REQUEST, mac)
            else:
                self.logger.info(
                    "Received node available message for node %s which is already joined.",
                    mac,
                )
        else:
            if self._plugwise_nodes.get(mac):
                self._plugwise_nodes[mac].on_message(message)

    def message_processed(self, seq_id, ack_response=None):
        """ Execute callback of received messages """
        if seq_id in self.expected_responses:
            # excute callback at response of message
            self.logger.debug(
                "%s request with seq id %s processed",
                self.expected_responses[seq_id][0].__class__.__name__,
                str(seq_id),
            )
            if isinstance(self.expected_responses[seq_id][1], StickInitRequest):
                if self.expected_responses[seq_id][2]:
                    self.expected_responses[seq_id][2]()
            else:
                if ack_response == ACK_TIMEOUT:
                    if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                        mac = self.expected_responses[seq_id][1].mac.decode("ascii")
                        self.logger.debug(
                            "Network time out received for (%s of %s) of %s to %s, resend request",
                            str(self.expected_responses[seq_id][3] + 1),
                            str(MESSAGE_RETRY + 1),
                            str(self.expected_responses[seq_id][1].__class__.__name__),
                            mac,
                        )
                        if self._plugwise_nodes.get(mac):
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
                        mac = self.expected_responses[seq_id][1].mac.decode("ascii")
                        if self._plugwise_nodes.get(mac):
                            if self._plugwise_nodes[mac].get_available():
                                self.logger.info(
                                    "Mark %s as unavailabe because %s time out responses reached",
                                    mac,
                                    str(MESSAGE_RETRY + 1),
                                )
                                self._plugwise_nodes[mac].set_available(False)
                elif ack_response == ACK_ERROR:
                    mac = self.expected_responses[seq_id][1].mac.decode("ascii")
                    if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                        self.logger.debug(
                            "Error response received for (%s of %s) of %s to %s, resend request",
                            str(self.expected_responses[seq_id][3] + 1),
                            str(MESSAGE_RETRY + 1),
                            str(self.expected_responses[seq_id][1].__class__.__name__),
                            mac,
                        )
                        if self._plugwise_nodes.get(mac):
                            if self._plugwise_nodes[mac].get_available():
                                self.send(
                                    self.expected_responses[seq_id][1],
                                    self.expected_responses[seq_id][2],
                                    self.expected_responses[seq_id][3] + 1,
                                )
                    else:
                        self.logger.debug(
                            "Error response received for (%s of %s) of %s to %s, drop request",
                            str(self.expected_responses[seq_id][3] + 1),
                            str(MESSAGE_RETRY + 1),
                            str(self.expected_responses[seq_id][1].__class__.__name__),
                            mac,
                        )
                elif ack_response == None:
                    if self.expected_responses[seq_id][2]:
                        try:
                            self.expected_responses[seq_id][2]()
                        except Exception as e:
                            self.logger.error(
                                "Error while executing callback after processing message : %s",
                                e,
                            )
            del self.expected_responses[seq_id]

    def _watchdog_loop(self):
        """
        Main worker loop to watch all other worker threads
        """
        time.sleep(5)
        circle_plus_retry_counter = 0
        while self._run_watchdog:
            # Connection
            if self.connection.is_connected():
                # Connection reader daemon
                if not self.connection.read_thread_alive():
                    self.logger.warning("Unexpected halt of connection reader thread")
                # Connection writer daemon
                if not self.connection.write_thread_alive():
                    self.logger.warning("Unexpected halt of connection writer thread")
            # receive timeout daemon
            if self._run_receive_timeout_thread:
                if not self._receive_timeout_thread.isAlive():
                    self.logger.warning(
                        "Unexpected halt of receive thread, restart thread",
                    )
                    self._receive_timeout_thread = threading.Thread(
                        None,
                        self._receive_timeout_loop,
                        "receive_timeout_thread",
                        (),
                        {},
                    )
                    self._receive_timeout_thread.daemon = True
                    self._receive_timeout_thread.start()
            # send message deamon
            if self._run_send_message_thread:
                if not self._send_message_thread.isAlive():
                    self.logger.warning(
                        "Unexpected halt of send thread, restart thread",
                    )
                    self._send_message_thread = threading.Thread(
                        None, self._send_message_loop, "send_messages_thread", (), {}
                    )
                    self._send_message_thread.daemon = True
                    self._send_message_thread.start()
            # Update daemon
            if self._run_update_thread:
                if not self._update_thread.isAlive():
                    self.logger.warning(
                        "Unexpected halt of update thread, restart thread",
                    )
                    self._run_update_thread = True
                    self._update_thread = threading.Thread(
                        None, self._update_loop, "update_thread", (), {}
                    )
                    self._update_thread.daemon = True
                    self._update_thread.start()
            # Circle+ discovery
            if self._circle_plus_discovered == False:
                # First hour every once an hour
                if self._circle_plus_retries < 60 or circle_plus_retry_counter > 60:
                    self.logger.info(
                        "Circle+ not yet discovered, resubmit discovery request",
                    )
                    self.discover_node(self.circle_plus_mac, self.scan)
                    self._circle_plus_retries += 1
                    circle_plus_retry_counter = 0
                circle_plus_retry_counter += 1
            time.sleep(WATCHDOG_DEAMON)

    def _update_loop(self):
        """
        When node has not received any message during
        last 2 update polls, reset availability
        """
        self._run_update_thread = True
        self._auto_update_first_run = True
        day_of_month = datetime.now().day
        try:
            while self._run_update_thread:
                for mac in self._plugwise_nodes:
                    if self._plugwise_nodes[mac]:
                        # Do ping request
                        self.logger.debug(
                            "Send ping to node %s", mac,
                        )
                        self._plugwise_nodes[mac].ping()
                    # Only power use updates for supported nodes
                    if isinstance(
                        self._plugwise_nodes[mac], PlugwiseCircle
                    ) or isinstance(self._plugwise_nodes[mac], PlugwiseCirclePlus):
                        # Don't check at first time
                        self.logger.debug(
                            "Request current power usage for node %s", mac
                        )
                        if not self._auto_update_first_run and self._run_update_thread:
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
                                # Refresh node info once per hour and request power use afterwards
                                if self._plugwise_nodes[mac]._last_info_message != None:
                                    if self._plugwise_nodes[mac]._last_info_message < (
                                        datetime.now().replace(
                                            minute=1,
                                            second=MAX_TIME_DRIFT,
                                            microsecond=0,
                                        )
                                    ):
                                        self._plugwise_nodes[mac]._request_info(
                                            self._plugwise_nodes[
                                                mac
                                            ]._request_power_buffer
                                        )
                                if not self._plugwise_nodes[mac]._last_log_collected:
                                    self._plugwise_nodes[mac]._request_power_buffer()
                        else:
                            if self._run_update_thread:
                                self.logger.debug(
                                    "First request for current power usage for node %s",
                                    mac,
                                )
                                self._plugwise_nodes[mac].update_power_usage()
                self._auto_update_first_run = False

                # Try to rediscover node(s) which where not available at initial scan
                # Do this the first hour at every update, there after only once an hour
                for mac in self._nodes_not_discovered:
                    (firstrequest, lastrequest) = self._nodes_not_discovered[mac]
                    if firstrequest and lastrequest:
                        if (firstrequest + timedelta(hours=1)) > datetime.now():
                            # first hour, so do every update a request
                            self.discover_node(mac, self._discover_after_scan)
                            self._nodes_not_discovered[mac] = (
                                firstrequest,
                                datetime.now(),
                            )
                        else:
                            if (lastrequest + timedelta(hours=1)) < datetime.now():
                                self.discover_node(mac, self._discover_after_scan)
                                self._nodes_not_discovered[mac] = (
                                    firstrequest,
                                    datetime.now(),
                                )
                    else:
                        self.discover_node(mac, self._discover_after_scan)
                        self._nodes_not_discovered[mac] = (
                            datetime.now(),
                            datetime.now(),
                        )
                # Sync internal clock of all available nodes once a day
                if datetime.now().day != day_of_month:
                    day_of_month = datetime.now().day
                    for mac in self._plugwise_nodes:
                        if self._plugwise_nodes[mac]:
                            if self._plugwise_nodes[mac].get_available():
                                self._plugwise_nodes[mac].sync_clock()
                if self._auto_update_timer:
                    time.sleep(self._auto_update_timer)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(
                "Error at line %s of _update_loop : %s", exc_tb.tb_lineno, e
            )

    def auto_update(self, timer=None):
        """
        setup auto update polling for power usage.
        """
        if timer == 0:
            self._run_update_thread = False
            self._auto_update_timer = None
        else:
            self._auto_update_timer = 5
            if timer == None:
                # Timer based on number of nodes and 3 seconds per node
                self._auto_update_timer = len(self._plugwise_nodes) * 3
            elif timer > 5:
                self._auto_update_timer = timer
            if not self._run_update_thread:
                self._update_thread.start()
