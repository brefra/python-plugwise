"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Circle plug object
"""
import logging
from plugwise.constants import *
from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    PlugCalibrationRequest,
    PlugInfoRequest,
    PlugPowerUsageRequest,
    PlugSwitchRequest,
)
from plugwise.messages.responses import (
    PlugCalibrationResponse,
    PlugInitResponse,
    PlugPowerUsageResponse,
    PlugSwitchResponse,
)
from plugwise.util import Int, validate_mac


class Plug(object):
    """provides interface to the Plugwise Plug & Plug+ devices
    """

    def __init__(self, mac, stick):
        """
        will raise ValueError if mac doesn't look valid
        """
        mac = mac.upper()
        if validate_mac(mac) == False:
            raise ValueError("MAC address is in unexpected format: " + str(mac))
        self._mac = bytes(mac, encoding="latin-1")
        self._callbacks = []
        self.last_update = None
        self._relay_state = None
        self._hardware_version = None
        self._firmware_version = None
        self._pulse_1s = None
        self._pulse_8s = None
        self._pulse_hour = None
        self._gain_a = None
        self._gain_b = None
        self._off_ruis = None
        self._off_tot = None
        self.stick = stick
        self.stick.logger.error("Initializing plug with mac %s", str(self._mac))
        self._request_info()
        self._request_calibration()

    def _request_info(self, callback=None):
        """ Request info from plug
        """
        self.stick.send(
            PlugInfoRequest(self._mac), callback,
        )

    def _request_calibration(self, callback=None):
        """Request calibration info
        """
        self.stick.send(
            PlugCalibrationRequest(self._mac), callback,
        )

    def _request_switch(self, state, callback=None):
        """Request to switch relay state and request state info
        """
        self.stick.send(
            PlugSwitchRequest(self._mac, state), callback,
        )

    def update_power_usage(self, callback=None):
        """Request power usage
        """
        self.stick.send(
            PlugPowerUsageRequest(self._mac), callback,
        )

    def new_message(self, message):
        """
        Process received message
        """
        self.stick.logger.debug(
            "Process received message for plug with mac %s", str(self._mac)
        )
        if isinstance(message, PlugwiseMessage):
            if message.mac == self._mac:
                if isinstance(message, PlugPowerUsageResponse):
                    self._response_power_usage(message)
                    if CALLBACK_POWER in self._callbacks:
                        for callback in self._callbacks[CALLBACK_POWER]:
                            callback(get_power_usage())
                elif isinstance(message, PlugSwitchResponse):
                    self._response_switch(message)
                    if CALLBACK_RELAY in self._callbacks:
                        for callback in self._callbacks[CALLBACK_RELAY]:
                            callback(self._relay_state)
                elif isinstance(message, PlugCalibrationResponse):
                    self._response_calibration(message)
                elif isinstance(message, PlugInitResponse):
                    self._response_info(message)
                self.stick.message_processed(message.seq_id)
            else:
                self.stick.logger.error(
                    "Skip message, mac message %s != mac plug %s",
                    str(self._mac),
                    str(message.mac),
                )
        else:
            self.stick.logger.warning("Wrong message type: %s", type(message))

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

    def _response_info(self, message):
        """ Process info response message
        """
        self.stick.logger.error(
            "Response info message for plug with mac " + str(self._mac)
        )
        if message.relay_state.serialize() == b"01":
            self._relay_state = True
        else:
            self._relay_state = False
        self.stick.logger.debug("Relay = " + str(self._relay_state))
        self._hardware_version = message.hw_ver
        self.stick.logger.debug("hw version = " + str(self._hardware_version.value))
        self.last_update = message.timestamp

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
