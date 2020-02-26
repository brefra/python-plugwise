# Use of this source code is governed by the MIT license found in the LICENSE file.

import logging
from plugwise.constants import (
    MESSAGE_FOOTER,
    MESSAGE_HEADER,
)
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import (
    CircleCalibrationResponse,
    CirclePowerUsageResponse,
    CircleSwitchResponse,
    NodeInfoResponse,
    StickInitResponse,
)
from plugwise.util import inc_seq_id


class PlugwiseParser(object):
    """
    Transform Plugwise message from wire format to response message object
    """

    def __init__(self, stick):
        self.stick = stick
        self._buffer = bytes([])
        self._parsing = False
        self._message = None

    def feed(self, data):
        """
        Add new incoming data to buffer and try to process
        """
        self.stick.logger.debug("Feed data: %s", str(data))
        self._buffer += data
        if len(self._buffer) >= 8:
            if self._parsing == False:
                self.parse_data()

    def next_message(self, message):
        """
        Process next packet if present
        """
        self.stick.new_message(message)

    def parse_data(self):
        """
        Process next set of packet data
        
        """
        self.stick.logger.debug("Parse data: %s ", str(self._buffer))
        if self._parsing == False:
            self._parsing = True

            # Lookup header of message in buffer
            self.stick.logger.debug(
                "Lookup message header (%s) in (%s)",
                str(MESSAGE_HEADER),
                str(self._buffer),
            )
            header_index = self._buffer.find(MESSAGE_HEADER)
            if header_index == -1:
                self.stick.logger.debug("No valid message header found yet")
            else:
                self.stick.logger.debug(
                    "Valid message header found at index %s", str(header_index)
                )
                self._buffer = self._buffer[header_index:]

                # Header available, lookup footer of message in buffer
                self.stick.logger.debug(
                    "Lookup message footer (%s) in (%s)",
                    str(MESSAGE_FOOTER),
                    str(self._buffer),
                )
                footer_index = self._buffer.find(MESSAGE_FOOTER)
                if footer_index == -1:
                    self.stick.logger.debug("No valid message footer found yet")
                else:
                    self.stick.logger.debug(
                        "Valid message footer found at index %s", str(footer_index)
                    )
                    if footer_index == 20:
                        # Acknowledge message
                        self.stick.logger.debug(
                            "Skip acknowledge message with sequence id : "
                            + str(self._buffer[8:12])
                        )
                        self.stick.last_ack_seq_id = self._buffer[8:12]                      
                    elif footer_index < 28:
                        self.stick.logger.warning(
                            "Message %s to small, skip parsing",
                            self._buffer[: footer_index + 2],
                        )
                    else:
                        # Check for stick init response
                        if self._buffer[4:8] == b"0011":
                            self._message = StickInitResponse()
                        else:
                            # Footer and Header available, lookup expected message
                            seq_id = self._buffer[8:12]
                            if seq_id in self.stick.expected_responses:
                                self._message = self.stick.expected_responses[seq_id][0]
                                self.stick.logger.debug(
                                    "Expected msgtype: %s",
                                    self._message.__class__.__name__,
                                )
                            else:
                                self.stick.logger.warning(
                                    "No expected message type found for sequence id %s",
                                    str(seq_id),
                                )
                    # Decode message
                    if isinstance(self._message, PlugwiseMessage):
                        if len(self._buffer[: footer_index + 2]) == len(self._message):
                            try:
                                self._message.unserialize(
                                    self._buffer[: footer_index + 2]
                                )
                                valid_message = True
                            except Exception as e:
                                self.stick.logger.error(
                                    "Error while decoding received message",
                                )
                                self.stick.logger.error(e)
                            # Submit message
                            if valid_message:
                                self.next_message(self._message)
                        else:
                            self.stick.logger.error(
                                "Skip message, received %s bytes of expected %s bytes",
                                len(self._buffer[: footer_index + 2]),
                                len(self._message),
                            )
                        # Parse remaining buffer
                        self.reset_parser(self._buffer[footer_index + 2 :])
                    else:
                        # skip this message, so remove header from buffer
                        self.reset_parser(self._buffer[6:])
            self._parsing = False
        else:
            self.stick.logger.debug("Skip parsing session")

    def reset_parser(self, new_buffer=bytes([])):
        self.stick.logger.debug("Reset parser : %s", new_buffer)
        if new_buffer == b"\x83":
            # Skip additional byte sometimes appended after footer
            self._buffer = bytes([])
        else:
            self._buffer = new_buffer
        self._message = None
        self._parsing = False
        if len(self._buffer) > 0:
            self.parse_data()
