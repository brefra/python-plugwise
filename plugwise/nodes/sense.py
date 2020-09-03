"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise Sense node object
"""
from plugwise.constants import (
    HA_SENSOR,
    SENSE_HUMIDITY_MULTIPLIER,
    SENSE_HUMIDITY_OFFSET,
    SENSE_TEMPERATURE_MULTIPLIER,
    SENSE_TEMPERATURE_OFFSET,
    SENSOR_AVAILABLE,
    SENSOR_HUMIDITY,
    SENSOR_TEMPERATURE,
)
from plugwise.nodes.sed import NodeSED
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import SenseReportResponse


class PlugwiseSense(NodeSED):
    """provides interface to the Plugwise Sense nodes"""

    def __init__(self, mac, address, stick):
        super().__init__(mac, address, stick)
        self.categories = (HA_SENSOR,)
        self.sensors = (
            SENSOR_AVAILABLE["id"],
            SENSOR_TEMPERATURE["id"],
            SENSOR_HUMIDITY["id"],
        )
        self._temperature = None
        self._humidity = None

    def get_node_type(self) -> str:
        """Return node type"""
        return "Sense"

    def get_temperature(self) -> int:
        """ Return the current temperature """
        return self._temperature

    def get_humidity(self) -> int:
        """ Return the current humidity """
        return self._humidity

    def _on_SED_message(self, message):
        """
        Process received message
        """
        if isinstance(message, SenseReportResponse):
            self._process_sense_report(message)
            self.stick.message_processed(message.seq_id)

    def _process_sense_report(self, message):
        """ process sense report message to extract current temperature and humidity values """
        if message.temperature.value != 65535:
            new_temperature = int(
                SENSE_TEMPERATURE_MULTIPLIER * (message.temperature.value / 65536)
                - SENSE_TEMPERATURE_OFFSET
            )
            if self._temperature != new_temperature:
                self._temperature = new_temperature
                self.stick.logger.debug(
                    "Sense report received from %s with new temperature level of %s",
                    self.get_mac(),
                    str(self._temperature),
                )
                self.do_callback(SENSOR_TEMPERATURE["id"])
        if message.humidity.value != 65535:
            new_humidity = int(
                SENSE_HUMIDITY_MULTIPLIER * (message.humidity.value / 65536)
                - SENSE_HUMIDITY_OFFSET
            )
            if self._humidity != new_humidity:
                self._humidity = new_humidity
                self.stick.logger.debug(
                    "Sense report received from %s with new humidity level of %s",
                    self.get_mac(),
                    str(self._humidity),
                )
                self.do_callback(SENSOR_HUMIDITY["id"])
