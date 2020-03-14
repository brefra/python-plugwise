"""
Use of this source code is governed by the MIT license found in the LICENSE file.

General node object to control associated plugwise nodes like: Circle+, Circle, Scan, Stealth
"""
from plugwise.constants import *
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import NodeInfoResponse, NodePingResponse
from plugwise.messages.requests import NodeInfoRequest, NodePingRequest
from plugwise.util import validate_mac


class PlugwiseNode(object):
    """provides interface to the Plugwise node devices
    """

    def __init__(self, mac, address, stick):
        """
        will raise ValueError if mac doesn't look valid
        """
        mac = mac.upper()
        if validate_mac(mac) == False:
            raise ValueError("MAC address is in unexpected format: " + str(mac))
        self.mac = bytes(mac, encoding="ascii")
        self.stick = stick
        self._address = address
        self._callbacks = {}
        self.last_update = None
        self.last_request = None
        self._available = False
        self.in_RSSI = None
        self.out_RSSI = None
        self.ping_ms = None
        self._node_type = None
        self._hardware_version = None
        self._firmware_version = None
        self._relay_state = False

    def get_available(self) -> bool:
        return self._available

    def set_available(self, state, request_info=False):
        if state == True:
            if self._available == False:
                self._available = True
                self.stick.logger.debug(
                    "Mark node %s available", self.mac.decode("ascii"),
                )
                self._do_all_callbacks()
                if request_info:
                    self._request_info()
        else:
            if self._available == True:
                self._available = False
                self.stick.logger.debug(
                    "Mark node %s unavailable", self.mac.decode("ascii"),
                )
                self._do_all_callbacks()

    def get_mac(self) -> str:
        """Return mac address"""
        return self.mac.decode("ascii")

    def get_name(self) -> str:
        """Return unique name"""
        return self.get_node_type() + " (" + str(self._address) + ")"

    def get_node_type(self) -> str:
        """Return Circle type"""
        if self._node_type == NODE_TYPE_CIRCLE:
            return "Circle"
        elif self._node_type == NODE_TYPE_CIRCLE_PLUS:
            return "Circle+"
        elif self._node_type == NODE_TYPE_SCAN:
            return "Scan"
        elif self._node_type == NODE_TYPE_SENSE:
            return "Sense"
        elif self._node_type == NODE_TYPE_STEALTH:
            return "Stealth"
        elif self._node_type == NODE_TYPE_SWITCH:
            return "Switch"
        elif self._node_type == NODE_TYPE_STICK:
            return "Stick"
        return "Unknown"

    def get_categories(self) -> str:
        return [HA_SWITCH]

    def get_hardware_version(self) -> str:
        """Return hardware version"""
        if self._hardware_version != None:
            return self._hardware_version
        return "Unknown"

    def get_firmware_version(self) -> str:
        """Return firmware version"""
        if self._firmware_version != None:
            return str(self._firmware_version)
        return "Unknown"

    def get_last_update(self) -> str:
        """Return  version"""
        return self.last_update

    def get_in_RSSI(self) -> int:
        """Return inbound RSSI level"""
        if self.in_RSSI != None:
            return self.in_RSSI
        return 0

    def get_out_RSSI(self) -> int:
        """Return outbound RSSI level"""
        if self.out_RSSI != None:
            return self.out_RSSI
        return 0

    def get_ping(self) -> int:
        """Return ping roundtrip"""
        if self.ping_ms != None:
            return self.ping_ms
        return 0

    def _request_info(self, callback=None):
        """ Request info from node"""
        self.stick.send(
            NodeInfoRequest(self.mac), callback,
        )

    def ping(self, callback=None):
        """ Ping node"""
        self.stick.send(
            NodePingRequest(self.mac), callback,
        )

    def on_message(self, message):
        """
        Process received message
        """
        assert isinstance(message, PlugwiseMessage)
        if message.mac == self.mac:
            if message.timestamp != None:
                self.stick.logger.debug(
                    "Last update %s of node %s, last message %s",
                    str(self.last_update),
                    self.mac.decode("ascii"),
                    str(message.timestamp),
                )
                self.last_update = message.timestamp
            if isinstance(message, NodeInfoResponse):
                self.set_available(True)
                self._process_info_response(message)
                self.stick.message_processed(message.seq_id)
            elif isinstance(message, NodePingResponse):
                self.in_RSSI = message.in_RSSI.value
                self.out_RSSI = message.out_RSSI.value
                self.ping_ms = message.ping_ms.value
                self.stick.message_processed(message.seq_id)
                self.set_available(True, True)
            else:
                self.set_available(True)
                self._on_message(message)
        else:
            self.stick.logger.debug(
                "Skip message, mac of node (%s) != mac at message (%s)",
                message.mac.decode("ascii"),
                self.mac.decode("ascii"),
            )

    def _on_message(self, message):
        pass

    def register_callback(self, callback, state=CALLBACK_ALL):
        """ Register callback to execute when state change happens """
        if state == CALLBACK_RELAY:
            if CALLBACK_RELAY not in self._callbacks:
                self._callbacks[CALLBACK_RELAY] = []
            self._callbacks[CALLBACK_RELAY].append(callback)
        if state == CALLBACK_POWER:
            if CALLBACK_POWER not in self._callbacks:
                self._callbacks[CALLBACK_POWER] = []
            self._callbacks[CALLBACK_POWER].append(callback)
        if state == CALLBACK_ALL:
            if CALLBACK_ALL not in self._callbacks:
                self._callbacks[CALLBACK_ALL] = []
            self._callbacks[CALLBACK_ALL].append(callback)

    def _do_all_callbacks(self):
        """ Execute callbacks registered for all updates """
        if CALLBACK_ALL in self._callbacks:
            for callback in self._callbacks[CALLBACK_ALL]:
                callback(None)

    def _process_info_response(self, message):
        """ Process info response message"""
        self.stick.logger.debug(
            "Response info message for plug %s", self.mac.decode("ascii")
        )
        if message.relay_state.serialize() == b"01":
            if not self._relay_state:
                self._relay_state = True
                self._do_all_callbacks()
        else:
            if self._relay_state:
                self._relay_state = False
                self._do_all_callbacks()
        self._hardware_version = int(message.hw_ver.value)
        self._firmware_version = message.fw_ver.value
        self._node_type = message.node_type.value
        self.stick.logger.debug("Node type        = %s", self.get_node_type())
        self.stick.logger.debug("Relay state      = %s", str(self._relay_state))
        self.stick.logger.debug("Hardware version = %s", str(self._hardware_version))
        self.stick.logger.debug("Firmware version = %s", str(self._firmware_version))
