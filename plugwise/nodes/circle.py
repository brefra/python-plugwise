"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Circle node object
"""
import logging
from datetime import date, datetime, timedelta
from plugwise.constants import (
    ACK_OFF,
    ACK_ON,
    MAX_TIME_DRIFT,
    SENSOR_AVAILABLE,
    SENSOR_PING,
    SENSOR_POWER_USE,
    SENSOR_POWER_USE_LAST_8_SEC,
    SENSOR_POWER_CONSUMPTION_CURRENT_HOUR,
    SENSOR_POWER_CONSUMPTION_PREVIOUS_HOUR,
    SENSOR_POWER_CONSUMPTION_TODAY,
    SENSOR_POWER_CONSUMPTION_YESTERDAY,
    SENSOR_POWER_PRODUCTION_CURRENT_HOUR,
    SENSOR_POWER_PRODUCTION_PREVIOUS_HOUR,
    SENSOR_RSSI_IN,
    SENSOR_RSSI_OUT,
    SWITCH_RELAY,
    HA_SWITCH,
    HA_SENSOR,
    PULSES_PER_KW_SECOND,
)
from plugwise.node import PlugwiseNode

from plugwise.message import PlugwiseMessage
from plugwise.messages.requests import (
    CircleCalibrationRequest,
    CircleClockGetRequest,
    CircleClockSetRequest,
    CirclePowerBufferRequest,
    CirclePowerUsageRequest,
    CircleSwitchRelayRequest,
)
from plugwise.messages.responses import (
    CircleCalibrationResponse,
    CircleClockResponse,
    CirclePowerBufferResponse,
    CirclePowerUsageResponse,
    CirclePlusScanResponse,
    NodeAckLargeResponse,
)
from plugwise.util import Int


class PlugwiseCircle(PlugwiseNode):
    """provides interface to the Plugwise Circle nodes and base class for Circle+ nodes"""

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self.categories = (HA_SWITCH, HA_SENSOR)
        self.sensors = (
            SENSOR_AVAILABLE["id"],
            SENSOR_PING["id"],
            SENSOR_POWER_USE["id"],
            SENSOR_POWER_USE_LAST_8_SEC["id"],
            SENSOR_POWER_CONSUMPTION_CURRENT_HOUR["id"],
            SENSOR_POWER_CONSUMPTION_PREVIOUS_HOUR["id"],
            SENSOR_POWER_CONSUMPTION_TODAY["id"],
            SENSOR_POWER_CONSUMPTION_YESTERDAY["id"],
            SENSOR_POWER_PRODUCTION_CURRENT_HOUR["id"],
            # SENSOR_POWER_PRODUCTION_PREVIOUS_HOUR["id"],
            SENSOR_RSSI_IN["id"],
            SENSOR_RSSI_OUT["id"],
        )
        self.switches = (SWITCH_RELAY["id"],)
        self.pulses_1s = None
        self.pulses_8s = None
        self.pulses_consumed_1h = None
        self.pulses_produced_1h = None
        self.calibration = False
        self._gain_a = None
        self._gain_b = None
        self._off_noise = None
        self._off_tot = None
        self.power_history = {}
        self.power_consumption_prev_hour = None
        self.power_consumption_today = None
        self.power_consumption_yesterday = None
        self._clock_offset = None
        self.get_clock(self.sync_clock)
        self._request_calibration()

    def _request_calibration(self, callback=None):
        """Request calibration info"""
        self.stick.send(
            CircleCalibrationRequest(self.mac),
            callback,
        )

    def _request_switch(self, state, callback=None):
        """Request to switch relay state and request state info"""
        self.stick.send(
            CircleSwitchRelayRequest(self.mac, state),
            callback,
        )

    def update_power_usage(self, callback=None):
        """Request power usage"""
        self.stick.send(
            CirclePowerUsageRequest(self.mac),
            callback,
        )

    def _on_message(self, message):
        """
        Process received message
        """
        if isinstance(message, CirclePowerUsageResponse):
            if self.calibration:
                self._response_power_usage(message)
                self.stick.logger.debug(
                    "Power update for %s, last update %s",
                    self.get_mac(),
                    str(self.last_update),
                )
            else:
                self.stick.logger.info(
                    "Received power update for %s before calibration information is known",
                    self.get_mac(),
                )
                self._request_calibration()
        elif isinstance(message, NodeAckLargeResponse):
            self._node_ack_response(message)
        elif isinstance(message, CircleCalibrationResponse):
            self._response_calibration(message)
        elif isinstance(message, CirclePowerBufferResponse):
            if self.calibration:
                self._response_power_buffer(message)
            else:
                self.stick.logger.debug(
                    "Received power buffer log for %s before calibration information is known",
                    self.get_mac(),
                )
                self._request_calibration()
        elif isinstance(message, CircleClockResponse):
            self._response_clock(message)
        else:
            self._circle_plus_message(message)

    def _circle_plus_message(self, message):
        pass

    def _process_scan_response(self, message):
        pass

    def get_relay_state(self) -> bool:
        """ Return last known relay state """
        return self._relay_state

    def set_relay_state(self, state: bool, callback=None):
        """ Switch relay """
        self._request_switch(state, callback)

    def get_power_usage(self):
        """
        Returns power usage during the last second in Watts
        Based on last received power usage information
        """
        if self.pulses_1s is not None:
            return self.pulses_to_kWs(self.pulses_1s) * 1000
        return None

    def get_power_usage_8_sec(self):
        """
        Returns power usage during the last 8 second in Watts
        Based on last received power usage information
        """
        if self.pulses_8s is not None:
            return self.pulses_to_kWs(self.pulses_8s, 8) * 1000
        return None

    def get_power_consumption_current_hour(self):
        """
        Returns the power usage during this running hour in kWh
        Based on last received power usage information
        """
        if self.pulses_consumed_1h is not None:
            return self.pulses_to_kWs(self.pulses_consumed_1h, 3600)
        return None

    def get_power_production_current_hour(self):
        """
        Returns the power production during this running hour in kWh
        Based on last received power usage information
        """
        if self.pulses_produced_1h is not None:
            return self.pulses_to_kWs(self.pulses_produced_1h, 3600)
        return None

    def get_power_consumption_prev_hour(self):
        """Returns power consumption during the previous hour in kWh"""
        return self.power_consumption_prev_hour

    def get_power_consumption_today(self):
        """Total power consumption during today in kWh"""
        return self.power_consumption_today

    def get_power_consumption_yesterday(self):
        """Total power consumption of yesterday in kWh"""
        return self.power_consumption_yesterday

    def _node_ack_response(self, message):
        """Process switch response message"""
        if message.ack_id == ACK_ON:
            if not self._relay_state:
                self.stick.logger.debug(
                    "Switch relay on for %s",
                    self.get_mac(),
                )
                self._relay_state = True
                self.do_callback(SWITCH_RELAY["id"])
        elif message.ack_id == ACK_OFF:
            if self._relay_state:
                self.stick.logger.debug(
                    "Switch relay off for %s",
                    self.get_mac(),
                )
                self._relay_state = False
                self.do_callback(SWITCH_RELAY["id"])
        else:
            self.stick.logger.debug(
                "Unmanaged _node_ack_response %s received for %s",
                str(message.ack_id),
                self.get_mac(),
            )

    def _response_power_usage(self, message):
        # Sometimes the circle returns -1 for some of the pulse counters
        # likely this means the circle measures very little power and is suffering from
        # rounding errors. Zero these out. However, negative pulse values are valid
        # for power producing appliances, like solar panels, so don't complain too loudly.

        # Power consumption last second
        if message.pulse_1s.value == -1:
            message.pulse_1s.value = 0
            self.stick.logger.debug(
                "1 sec power pulse counter for node %s has value of -1, corrected to 0",
                self.get_mac(),
            )
        self.pulses_1s = message.pulse_1s.value
        if message.pulse_1s.value != 0:
            if message.nanosecond_offset.value != 0:
                pulses_1s = (
                    message.pulse_1s.value
                    * (1000000000 + message.nanosecond_offset.value)
                ) / 1000000000
            else:
                pulses_1s = message.pulse_1s.value
            self.pulses_1s = pulses_1s
        else:
            self.pulses_1s = 0
        self.do_callback(SENSOR_POWER_USE["id"])
        # Power consumption last 8 seconds
        if message.pulse_8s.value == -1:
            message.pulse_8s.value = 0
            self.stick.logger.debug(
                "8 sec power pulse counter for node %s has value of -1, corrected to 0",
                self.get_mac(),
            )
        if message.pulse_8s.value != 0:
            if message.nanosecond_offset.value != 0:
                pulses_8s = (
                    message.pulse_8s.value
                    * (1000000000 + message.nanosecond_offset.value)
                ) / 1000000000
            else:
                pulses_8s = message.pulse_8s.value
            self.pulses_8s = pulses_8s
        else:
            self.pulses_8s = 0
        self.do_callback(SENSOR_POWER_USE_LAST_8_SEC["id"])
        # Power consumption current hour
        if message.pulse_hour_consumed.value == -1:
            message.pulse_hour_consumed.value = 0
            self.stick.logger.debug(
                "1 hour consumption power pulse counter for node %s has value of -1, corrected to 0",
                self.get_mac(),
            )
        self.pulses_consumed_1h = message.pulse_hour_consumed.value
        self.do_callback(SENSOR_POWER_CONSUMPTION_CURRENT_HOUR["id"])
        # Power produced current hour
        if message.pulse_hour_produced.value == -1:
            message.pulse_hour_produced.value = 0
            self.stick.logger.debug(
                "1 hour power production pulse counter for node %s has value of -1, corrected to 0",
                self.get_mac(),
            )
        self.pulses_produced_1h = message.pulse_hour_produced.value
        self.do_callback(SENSOR_POWER_PRODUCTION_CURRENT_HOUR["id"])

    def _response_calibration(self, message):
        """Store calibration properties"""
        for x in ("gain_a", "gain_b", "off_noise", "off_tot"):
            val = getattr(message, x).value
            setattr(self, "_" + x, val)
        self.calibration = True

    def pulses_to_kWs(self, pulses, seconds=1):
        """
        converts the amount of pulses to kWs using the calaboration offsets
        """
        if pulses == 0 or not self.calibration:
            return 0.0
        pulses_per_s = pulses / float(seconds)
        corrected_pulses = seconds * (
            (
                (((pulses_per_s + self._off_noise) ** 2) * self._gain_b)
                + ((pulses_per_s + self._off_noise) * self._gain_a)
            )
            + self._off_tot
        )
        calc_value = corrected_pulses / PULSES_PER_KW_SECOND / seconds
        # Fix minor miscalculations
        if calc_value < 0.001 and calc_value > -0.001:
            calc_value = 0.0
        return calc_value

    def _request_power_buffer(self, log_address=None, callback=None):
        """Request power log of specified address"""
        if log_address == None:
            log_address = self._last_log_address
        if log_address != None:
            if bool(self.power_history):
                # Only request last 2 power buffer logs
                self.stick.send(
                    CirclePowerBufferRequest(self.mac, log_address - 1),
                )
                self.stick.send(
                    CirclePowerBufferRequest(self.mac, log_address),
                    callback,
                )
            else:
                # Collect power history info of today and yesterday
                # Each request contains 4 hours except last request
                for req_log_address in range(log_address - 13, log_address):
                    self.stick.send(
                        CirclePowerBufferRequest(self.mac, req_log_address),
                    )
                self.stick.send(
                    CirclePowerBufferRequest(self.mac, log_address),
                    callback,
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
                if getattr(message, "pulses%d" % (i,)).value == 0:
                    self.power_history[dt] = 0.0
                else:
                    self.power_history[dt] = self.pulses_to_kWs(
                        getattr(message, "pulses%d" % (i,)).value, 3600
                    )
        # Cleanup history for more than 2 day's ago
        if len(self.power_history.keys()) > 48:
            for dt in list(self.power_history.keys()):
                if (dt + self.stick.timezone_delta - timedelta(hours=1)).date() < (
                    datetime.now().today().date() - timedelta(days=1)
                ):
                    del self.power_history[dt]
        # Recalculate power use counters
        last_hour_usage = 0
        today_power = 0
        yesterday_power = 0
        for dt in self.power_history:
            if (dt + self.stick.timezone_delta) == datetime.now().today().replace(
                minute=0, second=0, microsecond=0
            ):
                last_hour_usage = self.power_history[dt]
            if (
                dt + self.stick.timezone_delta - timedelta(hours=1)
            ).date() == datetime.now().today().date():
                today_power += self.power_history[dt]
            if (dt + self.stick.timezone_delta - timedelta(hours=1)).date() == (
                datetime.now().today().date() - timedelta(days=1)
            ):
                yesterday_power += self.power_history[dt]
        if self.power_consumption_prev_hour != last_hour_usage:
            self.power_consumption_prev_hour = last_hour_usage
            self.do_callback(SENSOR_POWER_CONSUMPTION_PREVIOUS_HOUR["id"])
        if self.power_consumption_today != today_power:
            self.power_consumption_today = today_power
            self.do_callback(SENSOR_POWER_CONSUMPTION_TODAY["id"])
        if self.power_consumption_yesterday != yesterday_power:
            self.power_consumption_yesterday = yesterday_power
            self.do_callback(SENSOR_POWER_CONSUMPTION_YESTERDAY["id"])

    def _response_clock(self, message):
        dt = datetime(
            datetime.now().year,
            datetime.now().month,
            datetime.now().day,
            message.time.value.hour,
            message.time.value.minute,
            message.time.value.second,
        )
        clock_offset = message.timestamp.replace(microsecond=0) - (
            dt + self.stick.timezone_delta
        )
        if clock_offset.days == -1:
            self._clock_offset = clock_offset.seconds - 86400
        else:
            self._clock_offset = clock_offset.seconds
        self.stick.logger.debug(
            "Clock of node %s has drifted %s sec",
            self.get_mac(),
            str(self._clock_offset),
        )

    def get_clock(self, callback=None):
        """ get current datetime of internal clock of Circle """
        self.stick.send(
            CircleClockGetRequest(self.mac),
            callback,
        )

    def set_clock(self, callback=None):
        """ set internal clock of CirclePlus """
        self.stick.send(
            CircleClockSetRequest(self.mac, datetime.utcnow()),
            callback,
        )

    def sync_clock(self, max_drift=0):
        """Resync clock of node if time has drifted more than MAX_TIME_DRIFT"""
        if self._clock_offset != None:
            if max_drift == 0:
                max_drift = MAX_TIME_DRIFT
            if (self._clock_offset > max_drift) or (self._clock_offset < -(max_drift)):
                self.stick.logger.info(
                    "Reset clock of node %s because time has drifted %s sec",
                    self.get_mac(),
                    str(self._clock_offset),
                )
                self.set_clock()
