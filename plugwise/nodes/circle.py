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

    def __init__(self, mac, stick):
        PlugwiseNode.__init__(self, mac, stick)
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
            if CALLBACK_POWER in self._callbacks:
                for callback in self._callbacks[CALLBACK_POWER]:
                    callback(self.get_power_usage())
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CircleSwitchResponse):
            self._response_switch(message)
            if CALLBACK_RELAY in self._callbacks:
                for callback in self._callbacks[CALLBACK_RELAY]:
                    callback(self._relay_state)
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CircleCalibrationResponse):
            self._response_calibration(message)
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CircleScanResponse):
            self._on_message(message)
        else:
            self.stick.logger.debug(
                "Unsupported message type '%s' received for circle with mac %s",
                str(message.__class__.__name__),
                self.get_mac(),
            )
            self.stick.message_processed(message.seq_id)

    def _status_update_callbacks(self, value):
        for callback in self._callbacks:
            callback(self._relay_state)

    def on_status_update(self, state, callback):
        """
        Callback to execute when status is updated
        """
        if state == CALLBACK_RELAY or state == CALLBACK_POWER:
            if state not in self._callbacks:
                self._callbacks[state] = []
            self._callbacks[state].append(callback)
        else:
            self.stick.logger.warning(
                "Wrong callback type '%s', should be '%s' or '%s'",
                state,
                CALLBACK_RELAY,
                CALLBACK_POWER,
            )

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
            self._relay_state = True
        else:
            self._relay_state = False

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
        self.last_update = message.timestamp

    def _response_calibration(self, message):
        for x in ("gain_a", "gain_b", "off_ruis", "off_tot"):
            val = getattr(message, x).value
            setattr(self, "_" + x, val)
        self.last_update = message.timestamp

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
        return pulses / PULSES_PER_KW_SECOND
