"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Scan node object
"""
from plugwise.constants import (
    HA_BINARY_SENSOR,
    SCAN_LIGHT_DETECTION,
    SCAN_MOTION_HIGH,
    SCAN_MOTION_MEDIUM,
    SCAN_MOTION_OFF,
    SCAN_MOTION_RESET_TIMER,
    SCAN_SENSITIVITY,
    SENSOR_AVAILABLE,
    SENSOR_MOTION,
)
from plugwise.nodes.sed import NodeSED
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import NodeSwitchGroupResponse
from plugwise.messages.requests import (
    ScanConfigRequest,
    ScanLightCalibrateRequest,
)


class PlugwiseScan(NodeSED):
    """provides interface to the Plugwise Scan nodes"""

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self.categories = (HA_BINARY_SENSOR,)
        self.sensors = (
            SENSOR_AVAILABLE["id"],
            SENSOR_MOTION["id"],
        )
        self._motion_state = False
        self._motion_reset_timer = None
        self._light_detection = None
        self._sensitivity = None

    def get_node_type(self) -> str:
        """Return node type"""
        return "Scan"

    def get_motion(self) -> bool:
        """ Return motion state"""
        return self._motion_state

    def _on_SED_message(self, message):
        """
        Process received message
        """
        if isinstance(message, NodeSwitchGroupResponse):
            self.stick.logger.debug(
                "Switch group request %s received from %s for group %s",
                str(message.power_state.value),
                self.get_mac(),
                str(message.group.value),
            )
            self._process_switch_group(message)
            self.stick.message_processed(message.seq_id)

    def _process_switch_group(self, message):
        """Switch group request from Scan"""
        if message.power_state.value == 0:
            # turn off => clear motion
            if self._motion:
                print("_motion=False")
                self._motion_state = False
                self.do_callback(SENSOR_MOTION["id"])
        elif message.power_state.value == 1:
            # turn on => motion
            if not self._motion:
                print("_motion=True")
                self._motion_state = True
                self.do_callback(SENSOR_MOTION["id"])
        else:
            print("_motion = " + str(message.power_state.value))
            self.stick.logger.debug(
                "Unknown power_state (%s) received from %s",
                str(message.power_state.value),
                self.get_mac(),
            )

    def CalibrateLight(self, callback=None):
        """Queue request to calibration light sensitivity"""
        self._send_request(ScanLightCalibrateRequest(self.mac), callback)

    def ConfigureMotion(
        self,
        motion_reset_timer=SCAN_MOTION_RESET_TIMER,
        sensitivity=SCAN_SENSITIVITY,
        light_detection=SCAN_LIGHT_DETECTION,
        callback=None,
    ):
        """Queue request to set motion reporting settings"""
        self._motion_reset_timer = motion_reset_timer
        self._light_detection = light_detection
        self._sensitivity = sensitivity
        self._send_request(
            ScanConfigRequest(self.mac, motion_reset, sensitivity, light_detection),
            callback,
        )

