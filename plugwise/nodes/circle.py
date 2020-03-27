"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Circle node object
"""
import logging
from datetime import date, datetime, timedelta
from plugwise.constants import (
    CALLBACK_POWER,
    CALLBACK_RELAY,
    HA_SWITCH,
    HA_SENSOR,
    PULSES_PER_KW_SECOND,
)
from plugwise.node import PlugwiseNode

from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CircleCalibrationRequest,
    CirclePowerBufferRequest,
    CirclePowerUsageRequest,
    CircleSwitchRequest,
)
from plugwise.messages.responses import (
    CircleCalibrationResponse,
    CirclePowerBufferResponse,
    CirclePowerUsageResponse,
    CircleScanResponse,
    CircleSwitchResponse,
)
from plugwise.util import Int


class PlugwiseCircle(PlugwiseNode):
    """provides interface to the Plugwise Circle nodes
    """

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self._pulse_1s = None
        self._pulse_8s = None
        self._pulse_hour = None
        self._gain_a = None
        self._gain_b = None
        self._off_ruis = None
        self._off_tot = None
        self._power_history = {}
        self._power_use_last_hour = 0
        self._power_use_today = 0
        self._power_use_yesterday = 0
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
            self.stick.logger.debug(
                "Power update for %s, last update %s",
                self.get_mac(),
                str(self.last_update),
            )
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CircleSwitchResponse):
            self._response_switch(message)
            self.stick.logger.debug(
                "Switch update for %s, last update %s",
                self.get_mac(),
                str(self.last_update),
            )
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CircleCalibrationResponse):
            self._response_calibration(message)
            self.stick.message_processed(message.seq_id)
        elif isinstance(message, CirclePowerBufferResponse):
            self._response_power_buffer(message)
            self.stick.message_processed(message.seq_id)
        else:
            self._circle_plus_message(message)
        
    def _circle_plus_message(self, message):
        pass

    def _process_scan_response(self, message):
        pass

    def _do_circle_callbacks(self, callback_type):
        """ Execute callbacks registered for power and relay updates """
        if callback_type == CALLBACK_RELAY:
            if CALLBACK_RELAY in self._callbacks:
                for callback in self._callbacks[CALLBACK_RELAY]:
                    try:
                        callback(self._relay_state)
                    except Exception as e:
                        self.stick.logger.error(
                            "Error while executing relay callback : %s",
                            e,
                        )
        elif callback_type == CALLBACK_POWER:
            if CALLBACK_POWER in self._callbacks:
                for callback in self._callbacks[CALLBACK_POWER]:
                    try:
                        callback(self.get_power_usage())
                    except Exception as e:
                        self.stick.logger.error(
                            "Error while executing power callback : %s",
                            e,
                        )
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

    def get_power_use_last_hour(self):
        return self._power_use_last_hour

    def get_power_use_today(self):
        return self._power_use_today

    def get_power_use_yesterday(self):
        return self._power_use_yesterday

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

    def _request_power_buffer(self, log_address=None, callback=None):
        """Request power log of specified address
        """
        if log_address == None:
            log_address = self._last_log_address
        if log_address != None:
            if bool(self._power_history):
                # Only request last power log
                self.stick.send(
                    CirclePowerBufferRequest(self.mac, log_address), callback,
                )
            else:
                # Collect power history info of today and yesterday
                # Each request contains 4 hours except last request
                for req_log_address in range(log_address - 13, log_address):
                    self.stick.send(
                        CirclePowerBufferRequest(self.mac, req_log_address),
                    )
                self.stick.send(
                    CirclePowerBufferRequest(self.mac, log_address), callback,
                )
        
    def _response_power_buffer(self, message):
        """returns information about historical power usage
        each response contains 4 log buffers and each log buffer contains data for 1 hour
        """
        if message.logaddr.value == self._last_log_address:
            self._last_log_collected = True

        # Collect logged power usage
        for i in range(1, 5):
            if getattr(message, "logdate%d" % (i,)).value != None:
                dt = getattr(message, "logdate%d" % (i,)).value
                corrected_pulses = self._pulse_correction(getattr(message, "pulses%d" % (i,)).value, 3600)
                self._power_history[dt] = self._pulses_to_kWs(corrected_pulses)

        # Cleanup history for more than 2 day's ago
        if len(self._power_history.keys()) > 48:
            for dt in list(self._power_history.keys()):
                if (dt + self.stick.timezone_delta - timedelta(hours=1)).date() < (datetime.now().today().date() - timedelta(days=1)):
                    del self._power_history[dt]

        # Recalculate power use counters        
        last_hour_usage = 0
        today_power = 0
        yesterday_power = 0
        for dt in self._power_history:
            if (dt + self.stick.timezone_delta) == datetime.now().today().replace(minute=0, second=0, microsecond=0):
                last_hour_usage = self._power_history[dt]
            if (dt + self.stick.timezone_delta - timedelta(hours=1)).date() == datetime.now().today().date():
                today_power += self._power_history[dt]
            if (dt + self.stick.timezone_delta - timedelta(hours=1)).date() == (datetime.now().today().date() - timedelta(days=1)):
                yesterday_power += self._power_history[dt]
        do_callback = False
        if self._power_use_last_hour != last_hour_usage:
            self._power_use_last_hour = last_hour_usage
            do_callback = True
        if self._power_use_today != round(today_power, 3):
            self._power_use_today = round(today_power, 3)
            do_callback = True
        if self._power_use_yesterday != round(yesterday_power, 3):
            self._power_use_yesterday = round(yesterday_power, 3)
            do_callback = True
        if do_callback:
            self._do_circle_callbacks(CALLBACK_POWER)
            self.stick.logger.debug(
                "Recalc powerusage for %s : h=%s, t=%s, y=%s",
                self.get_mac(),
                str(self._power_use_last_hour),
                str(self._power_use_today),
                str(self._power_use_yesterday),
            )
