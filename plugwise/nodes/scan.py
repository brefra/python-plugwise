"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Scan node object
"""
from plugwise.constants import (
    HA_BINARY_SENSOR_MOTION,
    SCAN_MOTION_RESET,
    SCAN_SENSITIVITY,
    SENSOR_AVAILABLE,
    SENSOR_MOTION,
)
from plugwise.node import PlugwiseSED
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import NodeSwitchGroupResponse
from plugwise.messages.requests import NodeSwitchGroupRequest, SEDSleepConfigRequest, ScanLightCalibrateRequest


class PlugwiseScan(PlugwiseSED):
    """provides interface to the Plugwise Scan nodes
    """

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self.categories = (HA_BINARY_SENSOR_MOTION)
        self.sensors = (
            SENSOR_AVAILABLE["id"],
            SENSOR_MOTION["id"],
        )
        self._motion = False
        self._light = False

    def get_node_type(self) -> str:
        """Return node type"""
        return "Scan"

    def get_motion(self):
        """ Return motion state"""
        return self._motion

    def _on_SED_message(self, message):
        """
        Process received message
        """
        if isinstance(message, NodeSwitchGroupResponse):
            self.stick.logger.debug(
                "Switch group request %s received from %s for group id %s",
                str(message.power_state),
                self.get_mac(),
                str(message.group),
            )
            self._process_switch_group(message)
            self.stick.message_processed(message.seq_id)

    def _process_switch_group(self, message):
        """Switch group request from Scan"""
        if message.power_state == 0:
            # turn off => clear motion
            if self._motion:
                self._motion = False
                self.do_callback(SENSOR_MOTION["id"])
        elif message.power_state == 1:
            # turn on => motion
            if not self._motion:
                self._motion = True
                self.do_callback(SENSOR_MOTION["id"])
        else:
            self.stick.logger.debug(
                "Unknown power_state (%s) received from %s",
                str(message.power_state),
                self.get_mac(),
            )

    def ConfigureSleep(self, awake_duration=SCAN_AWAKE_DURATION, sleep_duration=SED_SLEEP_DURATION, wake_up_interval=SED_AWAKE_INTERVAL, callback=None):
        """Queue sleep configuration config"""
        message = SEDSleepConfigRequest(self.mac, awake_duration, sleep_duration, wake_up_interval)
        self._send_request(message, callback)

    def CalibrateLight(self, callback=None):
        """Queue request to calibration light sensitivity
        """
        self._send_request(ScanLightCalibrateRequest(self.mac), callback)

