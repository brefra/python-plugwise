# Use of this source code is governed by the MIT license found in the LICENSE file.

import logging
from plugwise.constants import (
    MESSAGE_FOOTER,
    MESSAGE_HEADER,
)
from plugwise.message import PlugwiseMessage
from plugwise.messages.responses import (
    CircleCalibrationResponse,  # 0027
    CirclePlusConnectResponse,  # 0005
    CirclePlusQueryEndResponse,  # 0003
    CirclePlusQueryResponse,  # 0002
    CirclePlusRealTimeClockResponse,  # 003A
    CirclePlusScanResponse,  # 0019
    CirclePowerBufferResponse,  # 0049
    CirclePowerUsageResponse,  # 0013
    CircleClockResponse,  # 003F
    NodeAckLargeResponse,  # 0000
    NodeAckResponse,  # 0100
    NodeAckSmallResponse,  # 0000
    NodeFeaturesResponse,  # 0060
    NodeInfoResponse,  # 0024
    NodeJoinAvailableResponse,  # 0006
    NodeJoinAckResponse,  # 0061
    NodePingResponse,  # 000E
    NodeSwitchGroupResponse,  # 0056
    NodeRemoveResponse,  # 001D
    NodeAwakeResponse,  # 004F
    SenseReportResponse,  # 0105
    StickInitResponse,  # 0011
)


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
            if not self._parsing:
                self.parse_data()

    def next_message(self, message):
        """
        Process next packet if present
        """
        try:
            self.stick.new_message(message)
        except Exception as e:
            self.stick.logger.error(
                "Error while processing %s message : %s",
                self._message.__class__.__name__,
                e,
            )

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
                    seq_id = self._buffer[8:12]
                    # First check for known sequence ID's
                    if seq_id == b"FFFD":
                        self._message = NodeJoinAckResponse()
                    elif seq_id == b"FFFE":
                        self._message = NodeAwakeResponse()
                    elif seq_id == b"FFFF":
                        self._message = NodeSwitchGroupResponse()
                    else:
                        # No fixed sequence ID, Continue at message ID
                        message_id = self._buffer[4:8]
                        if message_id == b"0000":
                            if footer_index == 20:
                                # Short acknowledge message without MAC
                                self._message = NodeAckSmallResponse()
                            elif footer_index == 36:
                                # Large ack message with a MAC
                                self._message = NodeAckLargeResponse()
                            else:
                                self.stick.logger.error(
                                    "Skip unknown ACK message size of %s : %s",
                                    str(footer_index + 2),
                                    str(self._buffer[: footer_index + 2]),
                                )
                        elif message_id == b"0002":
                            self._message = CirclePlusQueryResponse()
                        elif message_id == b"0003":
                            self._message = CirclePlusQueryEndResponse()
                        elif message_id == b"0005":
                            self._message = CirclePlusConnectResponse()
                        elif message_id == b"0006":
                            self._message = NodeJoinAvailableResponse()
                        elif message_id == b"000E":
                            self._message = NodePingResponse()
                        elif message_id == b"0011":
                            self._message = StickInitResponse()
                        elif message_id == b"0013":
                            self._message = CirclePowerUsageResponse()
                        elif message_id == b"0019":
                            self._message = CirclePlusScanResponse()
                        elif message_id == b"001D":
                            self._message = NodeRemoveResponse()
                        elif message_id == b"0024":
                            self._message = NodeInfoResponse()
                        elif message_id == b"0027":
                            self._message = CircleCalibrationResponse()
                        elif message_id == b"003A":
                            self._message = CirclePlusRealTimeClockResponse()
                        elif message_id == b"003F":
                            self._message = CircleClockResponse()
                        elif message_id == b"0049":
                            self._message = CirclePowerBufferResponse()
                        elif message_id == b"0060":
                            self._message = NodeFeaturesResponse()
                        elif message_id == b"0100":
                            self._message = NodeAckResponse()
                        elif message_id == b"0105":
                            self._message = SenseReportResponse()
                        elif footer_index < 28:
                            self.stick.logger.error(
                                "Received message %s to small, skip parsing",
                                self._buffer[: footer_index + 2],
                            )
                        else:
                            # Lookup expected message based on request
                            self.stick.logger.info(
                                "Unknown message received, id=%s, data=%s",
                                str(message_id),
                                str(self._buffer[: footer_index + 2]),
                            )
                            if message_id != b"0000":
                                self.stick.logger.debug(
                                    "Message id %s",
                                    str(message_id),
                                )
                            if seq_id in self.stick.expected_responses:
                                self._message = self.stick.expected_responses[seq_id][0]
                                self.stick.logger.debug(
                                    "Expected %s for message id %s",
                                    self._message.__class__.__name__,
                                    str(message_id),
                                )
                            else:
                                self.stick.logger.debug(
                                    "No expected message type found for sequence id %s in %s",
                                    str(seq_id),
                                    self.stick.expected_responses.keys(),
                                )
                                self.stick.logger.debug(
                                    "Message %s",
                                    str(self._buffer[: footer_index + 2]),
                                )
                    # Decode message
                    if isinstance(self._message, PlugwiseMessage):
                        if len(self._buffer[: footer_index + 2]) == len(self._message):
                            valid_message = False
                            try:
                                self._message.deserialize(
                                    self._buffer[: footer_index + 2]
                                )
                                valid_message = True
                            except Exception as e:
                                self.stick.logger.error(
                                    "Error while decoding received %s message (%s)",
                                    self._message.__class__.__name__,
                                    str(self._buffer[: footer_index + 2]),
                                )
                                self.stick.logger.error(e)
                            # Submit message
                            if valid_message:
                                self.next_message(self._message)
                        else:
                            self.stick.logger.error(
                                "Skip message, received %s bytes of expected %s bytes for message %s",
                                len(self._buffer[: footer_index + 2]),
                                len(self._message),
                                self._message.__class__.__name__,
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
