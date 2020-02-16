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
    CircleScanRequest,
    CircleCalibrationRequest,
    NodeInfoRequest,
    CirclePowerUsageRequest,
    CircleSwitchRequest,
    NodeRequest,
    StickInitRequest,
)
from plugwise.messages.responses import (
    CircleScanResponse,
    CircleCalibrationResponse,
    NodeInfoResponse,
    CirclePowerUsageResponse,
    CircleSwitchResponse,
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
        self._auto_update_timer = None
        self._auto_update_thread = None
        self.last_received_seq_id = None
        self.last_send_seq_id = None
        self.expected_responses = {}
        self._init_callback = callback
        if ":" in port:
            self.logger.debug("Open socket connection to Plugwise Zigbee stick")
            self.connection = SocketConnection(port, self)
        else:
            self.logger.debug("Open USB serial connection to Plugwise Zigbee stick")
            self.connection = PlugwiseUSBConnection(port, self)
        self.logger.debug("Send init request to Plugwise Zigbee stick")
        # timeout deamon
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
        self.send(StickInitRequest())

    def nodes(self) -> dict:
        """ Return mac addresses of known plugwise nodes """
        return self._plugwise_nodes.keys()

    def node(self, mac):
        """ Return specific Plugwise node object"""
        if mac in self._plugwise_nodes:
            return self._plugwise_nodes[mac]
        return None

    def discover_node(self, mac) -> bool:
        """ Discovery plugwise node """
        if validate_mac(mac) == True:
            self.send(
                NodeInfoRequest(bytes(mac, "ascii")),
            )
            return True
        return False

    def discovery_finished(self):
        """ callback when last scan is received """
        # ??
        print ("== discovery_finished ==")

    def _append_node(self, mac, node_type, node_info_message):
        """ Add Plugwise node to be controlled """
        if node_type == NODE_TYPE_CIRCLE:
            self._plugwise_nodes[mac] = PlugwiseCircle(mac, self, node_info_message)
        elif node_type == NODE_TYPE_CIRCLE_PLUS:
            self._plugwise_nodes[mac] = PlugwiseCirclePlus(mac, self, node_info_message)
        else:
            self.logger.warning("Unsupported node type '%s'", str(node_type))

    def _remove_node(self, mac):
        """
        remove circle from stick

        :return: None
        """
        del self._plugwise_nodes[mac]

    def feed_parser(self, data):
        """
        Feed parser with new data

        :return: None
        """
        assert isinstance(data, bytes)
        self.parser.feed(data)

    def parse(self, message):
        """
        :return: plugwise.Message or None
        """
        return self.parser.parse(message)

    def send(self, request, callback=None, retry_counter=0):
        """
        Submit request message into Plugwise Zigbee network
        and wait for expected response

        :return: None
        """
        assert isinstance(request, NodeRequest)
        if self.last_send_seq_id != None and self.last_send_seq_id != b"0000":
            new_seq_id = inc_seq_id(self.last_send_seq_id)
        else:
            if self.last_received_seq_id != None:
                new_seq_id = inc_seq_id(self.last_received_seq_id)
            else:
                new_seq_id = b"0000"
        self.last_send_seq_id = new_seq_id
        if isinstance(request, CirclePowerUsageRequest):
            self.expected_responses[new_seq_id] = [CirclePowerUsageResponse(), request, callback, retry_counter, None]
        elif isinstance(request, NodeInfoRequest):
            self.expected_responses[new_seq_id] = [NodeInfoResponse(), request, callback, retry_counter, None]
        elif isinstance(request, CircleSwitchRequest):
            self.expected_responses[new_seq_id] = [CircleSwitchResponse(), request, callback, retry_counter, None]
        elif isinstance(request, CircleCalibrationRequest):
            self.expected_responses[new_seq_id] = [CircleCalibrationResponse(), request, callback, retry_counter, None]
        elif isinstance(request, CircleScanRequest):
            self.expected_responses[new_seq_id] = [CircleScanResponse(), request, callback, retry_counter, None]
        elif isinstance(request, StickInitRequest):
            self.expected_responses[new_seq_id] = [StickInitResponse(), request, callback, retry_counter, None]
        #self.msg_callback[new_seq_id] = callback
        self._send_message_queue.put((request, new_seq_id))
        #self.connection.send(request)

    def _send_message_daemon(self):
        while True:
            (message, seq_id) = self._send_message_queue.get(block=True)
            self.connection.send(message)
            self.expected_responses[seq_id][4] = datetime.now()
            time.sleep(SLEEP_TIME)

    def _receive_timeout_daemon(self):
        while True:
            for seq_id in list(self.expected_responses.keys()):
                if self.expected_responses[seq_id][4] != None:
                    if self.expected_responses[seq_id][4] < (datetime.now() - timedelta(seconds=MESSAGE_TIME_OUT)):
                        self.logger.debug("Timeout expired for message with sequence ID %s", str(seq_id))
                        print(">> Timeout expired for message with sequence ID " + str(seq_id))
                        if self.expected_responses[seq_id][3] <= MESSAGE_RETRY:
                            self.logger.debug("Resend request %s", str(self.expected_responses[seq_id][1].__class__.__name__))
                            print(">> Resend request " + str(self.expected_responses[seq_id][1].__class__.__name__))
                            self.send(
                                self.expected_responses[seq_id][1],
                                self.expected_responses[seq_id][2],
                                self.expected_responses[seq_id][3] + 1,
                            )
                        else:
                            self.logger.warning("Max retries (%s) reached for %s request ", str(MESSAGE_RETRY), self.expected_responses[seq_id][1].__class__.__name__)
                            print(">> max retry reached for " + self.expected_responses[seq_id][1].__class__.__name__)
                        del self.expected_responses[seq_id]
            time.sleep(MESSAGE_TIME_OUT + 10)


    def new_message(self, message):
        """
        Received message from Plugwise Zigbee network
        :return: None
        """
        print ("New message (" +  str(message.seq_id) + ") " + str(message.__class__.__name__))
        self.logger.debug("New %s message (seq id = %s)", message.__class__.__name__, str(message.seq_id))
        if isinstance(message, NodeResponse):
            self.last_received_seq_id = message.seq_id
            if self.last_send_seq_id == message.seq_id:
                self.last_send_seq_id = None
            if isinstance(message, StickInitResponse):
                self._mac_stick = message.mac
                if message.network_is_online.value == 1:
                    self.network_online = True
                else:
                    self.network_online = False
                # Replace first 2 charactors by 00 for mac of circle+ node
                self.circle_plus_mac = '00' + message.circle_plus_mac.value[2:].decode("ascii")
                self.network_id = message.network_id.value
                # The first StickInitResponse gives the actual sequence ID
                if b"0000" in self.expected_responses:
                    self.message_processed(b"0000")
                else:
                    self.message_processed(message.seq_id)
                self.discover_node(self.circle_plus_mac)
            elif isinstance(message, NodeInfoResponse):
                mac = message.mac.decode("ascii")
                if not mac in self._plugwise_nodes:
                    self._append_node(mac, message.node_type.value, message)
                    self.message_processed(message.seq_id)
                else:
                    self._plugwise_nodes[mac].on_message(message)
            else:
                if message.mac.decode("ascii") in self._plugwise_nodes:
                    self._plugwise_nodes[message.mac.decode("ascii")].on_message(message)
        print("queue = " + str(self.expected_responses.keys()))

    def message_processed(self, seq_id):
        if seq_id in self.expected_responses:
            # excute callback at response of message
            if self.expected_responses[seq_id][2] != None:
                self.expected_responses[seq_id][2]()
            del self.expected_responses[seq_id]

    def stop(self):
        """
        Stop connection to Plugwise Zigbee network
        """
        if self._auto_update_thread != None:
            self._auto_update_thread.cancel()
        self.connection.stop()

    def _request_power_usage(self):
        for circle in self._plugwise_nodes:
            # When circle has not received any message during last 2 update polls, reset availability
            if self._plugwise_nodes[circle].last_update != None:
                print("last update for mac " + str(circle) + " at " + str(self._plugwise_nodes[circle].last_update))
                print("check: " + str((datetime.now() - timedelta(seconds=(self._auto_update_timer * 3)))))
                if self._plugwise_nodes[circle].last_update < (datetime.now() - timedelta(seconds=(self._auto_update_timer * 3))):
                    self._plugwise_nodes[circle].available = False
            self._plugwise_nodes[circle].update_power_usage()
        if self._auto_update_timer != None:
            self._auto_update_thread = threading.Timer(
                self._auto_update_timer, self._request_power_usage
            ).start()

    def auto_update(self, timer=None):
        """
        setup auto update polling for power usage.

        :return: bool
        """
        if timer == None:
            # Timer based on number of circles
            self._auto_update_timer = len(self.circles()) * 2
            self._request_power_usage()
            return True
        elif timer == 0:
            if self._auto_update_thread != None:
                self._auto_update_thread.cancel()
            self._auto_update_timer = None
            return False
        elif timer > 5:
            if self._auto_update_thread != None:
                self._auto_update_thread.cancel()
            self._auto_update_timer = timer
            self._request_power_usage()
            return True
        return False
