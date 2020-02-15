"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Main stick object to control associated plugwise plugs
"""
import logging
import time
import threading
from datetime import datetime, timedelta

from plugwise.connections.socket import SocketConnection
from plugwise.connections.serial import PlugwiseUSBConnection
from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CircleScanRequest,
    CircleCalibrationRequest,
    CircleInfoRequest,
    CirclePowerUsageRequest,
    CircleSwitchRequest,
    CircleRequest,
    StickInitRequest,
)
from plugwise.messages.responses import (
    CircleScanResponse,
    CircleCalibrationResponse,
    CircleInfoResponse,
    CirclePowerUsageResponse,
    CircleSwitchResponse,
    CircleResponse,
    StickInitResponse,
)
from plugwise.parser import PlugwiseParser
from plugwise.circle import Circle
from plugwise.util import inc_seq_id, validate_mac


class stick(object):
    """
    Plugwise connection stick
    """

    def __init__(self, port, callback=None):
        self.logger = logging.getLogger("plugwise")
        self.mac_stick = None
        self.network_online = False
        self.circle_mac = None
        self.network_id = None
        self.network_id_short = None
        self.parser = PlugwiseParser(self)
        self._circles = {}
        self._circles_to_load = []
        self._auto_update_timer = None
        self._auto_update_thread = None
        self.last_received_seq_id = None
        self.last_send_seq_id = None
        self.expect_msg_response = {}
        self.msg_callback = {}
        self._init_callback = callback
        if ":" in port:
            self.logger.debug("Open socket connection to Plugwise Zigbee stick")
            self.connection = SocketConnection(port, self)
        else:
            self.logger.debug("Open USB serial connection to Plugwise Zigbee stick")
            self.connection = PlugwiseUSBConnection(port, self)
        self.logger.debug("Send init request to Plugwise Zigbee stick")
        self.send(StickInitRequest())

    def circles(self):
        """
        :return: list of circles
        """
        return self._circles

    def circle(self, mac):
        """
        :return: circle
        """
        return self._circles[mac]

    def add_circle(self, mac):
        """
        Add circle to stick

        :return: bool
        """
        if validate_mac(mac) == True:
            self._circles[bytes(mac, "utf-8")] = Circle(mac, self)
            return True
        self.logger.error("Failed to add circle, invalid mac '%s'", mac)
        return False

    def remove_circle(self, mac):
        """
        remove circle from stick

        :return: None
        """
        del self._circles[mac]

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

    def send(self, request, callback=None):
        """
        Submit request message into Plugwise Zigbee network
        and wait for expected response

        :return: None
        """
        assert isinstance(request, CircleRequest)
        if self.last_send_seq_id != None and self.last_send_seq_id != b"0000":
            new_seq_id = inc_seq_id(self.last_send_seq_id)
        else:
            if self.last_received_seq_id != None:
                new_seq_id = inc_seq_id(self.last_received_seq_id)
            else:
                new_seq_id = b"0000"
        self.last_send_seq_id = new_seq_id
        if isinstance(request, CirclePowerUsageRequest):
            self.expect_msg_response[new_seq_id] = CirclePowerUsageResponse()
        elif isinstance(request, CircleInfoRequest):
            self.expect_msg_response[new_seq_id] = CircleInfoResponse()
        elif isinstance(request, CircleSwitchRequest):
            self.expect_msg_response[new_seq_id] = CircleSwitchResponse()
        elif isinstance(request, CircleCalibrationRequest):
            self.expect_msg_response[new_seq_id] = CircleCalibrationResponse()
        elif isinstance(request, CircleScanRequest):
            self.expect_msg_response[new_seq_id] = CircleScanResponse()
        elif isinstance(request, StickInitRequest):
            self.expect_msg_response[new_seq_id] = StickInitResponse()
        self.msg_callback[new_seq_id] = callback
        self.connection.send(request)

    def new_message(self, message):
        """
        Received message from Plugwise Zigbee network
        :return: None
        """
        print ("New message " + str(message.__class__.__name__))
        self.logger.debug("New %s message", message.__class__.__name__)
        if isinstance(message, CircleResponse):
            self.last_received_seq_id = message.seq_id
            if self.last_send_seq_id == message.seq_id:
                self.last_send_seq_id = None
            if isinstance(message, StickInitResponse):
                self.mac_stick = message.mac
                if message.network_is_online.value == 1:
                    self.network_online = True
                else:
                    self.network_online = False
                self.circle_mac = b'00' + message.network_id.value[2:]
                self.network_id = message.network_id.value
                self.network_id_short = message.network_id_short.value
                if b"0000" in self.expect_msg_response:
                    self.message_processed(b"0000")
                else:
                    self.message_processed(message.seq_id)
                self.logger.debug("Query circle+ for known circle nodes")
                for node_id in range(0, 64):
                    self.send(CircleScanRequest(self.circle_mac, node_id))
            elif isinstance(message, CircleScanResponse):
                if message.node_mac.value != b'FFFFFFFFFFFFFFFF':
                    self._circles_to_load.append(message.node_mac.value.decode("ascii"))
                    self.logger.debug("Found circle with mac %s", message.node_mac.value.decode("ascii"))
                self.message_processed(message.seq_id)
                if message.node_id.value == 63:
                    # Last scan response
                    for new_circle in self._circles_to_load:
                        if not new_circle in self._circles:
                            self._circles[bytes(new_circle, "utf-8")] = Circle(new_circle, self)
                    if self._init_callback != None:
                        self._init_callback()
                    self.logger.debug("finished scan of plugwise network")
            else:
                if message.mac in self._circles:
                    self._circles[message.mac].new_message(message)
        print("queue = " + str(self.expect_msg_response.keys()))

    def message_processed(self, seq_id):
        pre_seq_id = inc_seq_id(seq_id, -1)
        while pre_seq_id in self.expect_msg_response:
            self.logger.warning("Failed to received message with sequence ID %s", str(pre_seq_id))
            del self.expect_msg_response[pre_seq_id]
            del self.msg_callback[pre_seq_id]
            pre_seq_id = inc_seq_id(pre_seq_id, -1)
            # TODO: do an action for missed response?

        if seq_id in self.expect_msg_response:
            del self.expect_msg_response[seq_id]
        if seq_id in self.msg_callback:
            # excute callback
            if self.msg_callback[seq_id] != None:
                self.msg_callback[seq_id]()
            del self.msg_callback[seq_id]

    def stop(self):
        """
        Stop connection to Plugwise Zigbee network
        """
        if self._auto_update_thread != None:
            self._auto_update_thread.cancel()
        self.connection.stop()

    def _request_power_usage(self):
        for circle in self._circles:
            # When circle has not received any message during last 2 update polls, reset availability
            if self._circles[circle].last_update != None:
                print("last update for mac " + str(circle) + " at " + str(self._circles[circle].last_update))
                print("check: " + str((datetime.now() - timedelta(seconds=(self._auto_update_timer * 3)))))
                if self._circles[circle].last_update < (datetime.now() - timedelta(seconds=(self._auto_update_timer * 3))):
                    self._circles[circle].available = False
            self._circles[circle].update_power_usage()
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
            self._auto_update_timer = None
            return False
        elif timer > 5:
            if self._auto_update_thread != None:
                self._auto_update_thread.cancel()
            self._auto_update_timer = timer
            self._request_power_usage()
            return True
        return False
