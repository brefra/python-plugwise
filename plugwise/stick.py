"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Main stick object to control associated plugwise plugs
"""
import logging
import time
import threading

from plugwise.connections.socket import SocketConnection
from plugwise.connections.serial import PlugwiseUSBConnection
from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CircleScanRequest,
    PlugCalibrationRequest,
    PlugInfoRequest,
    PlugPowerUsageRequest,
    PlugSwitchRequest,
    PlugwiseRequest,
    StickInitRequest,
)
from plugwise.messages.responses import (
    CircleScanResponse,
    PlugCalibrationResponse,
    PlugInitResponse,
    PlugPowerUsageResponse,
    PlugSwitchResponse,
    PlugwiseResponse,
    StickInitResponse,
)
from plugwise.parser import PlugwiseParser
from plugwise.plug import Plug
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
        self._plugs = {}
        self._plugs_to_load = []
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

    def plugs(self):
        """
        :return: list of plugs
        """
        return self._plugs

    def plug(self, mac):
        """
        :return: plug
        """
        return self._plugs[mac]

    def add_plug(self, mac):
        """
        Add plug to stick

        :return: bool
        """
        if validate_mac(mac) == True:
            self._plugs[bytes(mac, "utf-8")] = Plug(mac, self)
            return True
        self.logger.error("Failed to add plug, invalid mac '%s'", mac)
        return False

    def remove_plug(self, mac):
        """
        remove plug from stick

        :return: None
        """
        del self._plugs[mac]

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
        assert isinstance(request, PlugwiseRequest)
        if self.last_send_seq_id != None and self.last_send_seq_id != b"0000":
            new_seq_id = inc_seq_id(self.last_send_seq_id)
        else:
            if self.last_received_seq_id != None:
                new_seq_id = inc_seq_id(self.last_received_seq_id)
            else:
                new_seq_id = b"0000"
        self.last_send_seq_id = new_seq_id
        if isinstance(request, PlugPowerUsageRequest):
            self.expect_msg_response[new_seq_id] = PlugPowerUsageResponse()
        elif isinstance(request, PlugInfoRequest):
            self.expect_msg_response[new_seq_id] = PlugInitResponse()
        elif isinstance(request, PlugSwitchRequest):
            self.expect_msg_response[new_seq_id] = PlugSwitchResponse()
        elif isinstance(request, PlugCalibrationRequest):
            self.expect_msg_response[new_seq_id] = PlugCalibrationResponse()
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
        if isinstance(message, PlugwiseResponse):
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
                self.logger.debug("Query circle+ plug for plugwise nodes")
                for node_id in range(0, 64):
                    self.send(CircleScanRequest(self.circle_mac, node_id))
            elif isinstance(message, CircleScanResponse):
                if message.node_mac.value != b'FFFFFFFFFFFFFFFF':
                    self._plugs_to_load.append(message.node_mac.value.decode("ascii"))
                    self.logger.debug("Found plug with mac %s", message.node_mac.value.decode("ascii"))
                self.message_processed(message.seq_id)
                if message.node_id.value == 63:
                    # Last scan response
                    for new_plug in self._plugs_to_load:
                        if not new_plug in self._plugs:
                            self._plugs[bytes(new_plug, "utf-8")] = Plug(new_plug, self)
                    sleep.time(5)
                    if self._init_callback != None:
                        self._init_callback()
                    self.logger.debug("finished scan of plugwise network")
            else:
                if message.mac in self._plugs:
                    self._plugs[message.mac].new_message(message)

    def message_processed(self, seq_id):
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
        for plug in self._plugs:
            self._plugs[plug].update_power_usage()
            time.sleep(0.5)
        self._auto_update_thread = threading.Timer(
            self._auto_update_timer, self._request_power_usage
        ).start()

    def auto_power_update(self, timer):
        """
        setup auto refresh for power usage.

        :return: bool
        """
        if timer > 5:
            if self._auto_update_thread != None:
                self._auto_update_thread.cancel()
            self._auto_update_timer = timer
            self._request_power_usage()
            return True
        return False
