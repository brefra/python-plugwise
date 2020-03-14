"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Circle node object
"""
import logging
from plugwise.constants import *
from plugwise.node import PlugwiseNode

from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CircleCalibrationRequest,
    CirclePowerUsageRequest,
    CircleSwitchRequest,
)
from plugwise.messages.responses import (
    CircleCalibrationResponse,
    CirclePowerUsageResponse,
    CircleScanResponse,
    CircleSwitchResponse,
)
from plugwise.util import Int


class PlugwiseCircle(PlugwiseNode):
    """provides interface to the Plugwise Circle nodes
    """

    def __init__(self, mac, address, stick):
        PlugwiseNode.__init__(self, mac, address, stick)
        self._pulse_1s = None
        self._pulse_8s = None
        self._pulse_hour = None
        self._gain_a = None
        self._gain_b = None
        self._off_ruis = None
        self._off_tot = None
        self._request_calibration()

    def _request_calibration(self, callback=None):
        """Request calibration info
        """
        self.stick.send(
            CircleCalibrationRequest(self.mac), callback,
        )

    def _request_switch(self, state, callback=None):
        """Request to switch relay state and request state info
        """
        self.stick.send(
            CircleSwitchRequest(self.mac, state), callback,
        )

    def update_power_usage(self, callback=None):
        """Request power usage
        """
        self.stick.send(
            CirclePowerUsageRequest(self.mac), callback,
        )

    def _on_message(self, message):
        """
        Process received message
        """
        if isinstance(message, CirclePowerUsageResponse):
            self._response_power_usage(message)
            self.stick.message_processed(message.seq_id)
            self.stick.logger.debug(
                "Power update for %s, last update %s",
                self.get_mac(),
                str(self.last_update),
            )
        elif isinstance(message, CircleSwitchResponse):
            self._response_switch(message)
            self.stick.message_processed(message.seq_id)
            self.stick.logger.debug(
                "Switch update for %s, last update %s",
                self.get_mac(),
                str(self.last_update),
            )
        elif isinstance(message, CircleCalibrationResponse):
            self._response_calibration(message)
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CircleScanResponse):
            self._process_scan_response(message)
            self.stick.message_processed(message.seq_id)
        else:
            self.stick.logger.debug(
                "Unsupported message type '%s' received for circle with mac %s",
                str(message.__class__.__name__),
                self.get_mac(),
            )
            self.stick.message_processed(message.seq_id)

    def _process_scan_response(self, message):
        pass

    def _do_circle_callbacks(self, callback_type):
        """ Execute callbacks registered for power and relay updates """
        if callback_type == CALLBACK_RELAY:
            if CALLBACK_RELAY in self._callbacks:
                for callback in self._callbacks[CALLBACK_RELAY]:
                    callback(self._relay_state)
        elif callback_type == CALLBACK_POWER:
            if CALLBACK_POWER in self._callbacks:
                for callback in self._callbacks[CALLBACK_POWER]:
                    callback(self.get_power_usage())
        self._do_all_callbacks()

    def get_categories(self) -> str:
        return [HA_SWITCH, HA_SENSOR]

    def is_on(self):
        """
        Check if relay of plug is turned on

        :return: bool
        """
        return self._relay_state

    def turn_on(self, callback=None):
        """Turn on relay switch
        """
        self._request_switch(True, callback)

    def turn_off(self, callback=None):
        """Turn off relay switch
        """
        self._request_switch(False, callback)

    def get_power_usage(self):
        """
        returns power usage for the last second in Watts

        return : int
        """
        if self._pulse_1s == None:
            return 0.0
        corrected_pulses = self._pulse_correction(self._pulse_1s)
        retval = self._pulses_to_kWs(corrected_pulses) * 1000
        # sometimes it's slightly less than 0, probably caused by calibration/calculation errors
        # it doesn't make much sense to return negative power usage in that case
        return retval if retval > 0.0 else 0.0

    def _response_switch(self, message):
        """ Process switch response message
        """
        if message.relay_state == b"D8":
            if not self._relay_state:
                self._relay_state = True
                self._do_circle_callbacks(CALLBACK_RELAY)
        else:
            if self._relay_state:
                self._relay_state = False
                self._do_circle_callbacks(CALLBACK_RELAY)

    def _response_power_usage(self, message):
        # sometimes the circle returns max values for some of the pulse counters
        # I have no idea what it means but it certainly isn't a reasonable value
        # so I just assume that it's meant to signal some kind of a temporary error condition
        if message.pulse_1s.value == 65535:
            raise ValueError("1 sec pulse counter seem to contain unreasonable values")
        else:
            self._pulse_1s = message.pulse_1s.value
        if message.pulse_8s.value == 65535:
            raise ValueError("8 sec pulse counter seem to contain unreasonable values")
        else:
            self._pulse_8s = message.pulse_8s.value
        if message.pulse_hour.value == 4294967295:
            raise ValueError("1h pulse counter seems to contain an unreasonable value")
        else:
            self._pulse_hour = message.pulse_hour.value
        self._do_circle_callbacks(CALLBACK_POWER)


    def _response_calibration(self, message):
        for x in ("gain_a", "gain_b", "off_ruis", "off_tot"):
            val = getattr(message, x).value
            setattr(self, "_" + x, val)

    def _pulse_correction(self, pulses, seconds=1):
        """correct pulse count with Circle specific calibration offsets
        @param pulses: pulse counter
        @param seconds: over how many seconds were the pulses counted
        """
        if pulses == 0:
            return 0.0
        if self._gain_a is None:
            return None
        pulses /= float(seconds)
        corrected_pulses = seconds * (
            (
                (((pulses + self._off_ruis) ** 2) * self._gain_b)
                + ((pulses + self._off_ruis) * self._gain_a)
            )
            + self._off_tot
        )
        return corrected_pulses

    def _pulses_to_kWs(self, pulses):
        """converts the pulse count to kWs
        """
        if pulses != None:
            return pulses / PULSES_PER_KW_SECOND
        return 0
