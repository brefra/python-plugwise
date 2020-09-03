"""
Use of this source code is governed by the MIT license found in the LICENSE file.

All known request messages to be send to plugwise devices
"""
from plugwise.constants import (
    MESSAGE_FOOTER,
    MESSAGE_HEADER,
)
from plugwise.message import PlugwiseMessage
from plugwise.util import (
    DateTime,
    Int,
    LogAddr,
    String,
    RealClockDate,
    RealClockTime,
    Time,
)


class NodeRequest(PlugwiseMessage):
    """
    Base class for request messages to be send from by USB-Stick.
    """

    def __init__(self, mac):
        PlugwiseMessage.__init__(self)
        self.args = []
        self.mac = mac


class CirclePlusConnectRequest(NodeRequest):
    """
    Request to connect a Circle+ to the Stick

    Response message: CirclePlusConnectResponse
    """

    ID = b"0004"

    def __init__(self, mac):
        super().__init__(self, mac)

    # This message has an exceptional format and therefore need to override the serialize method
    def serialize(self):
        # This command has args: byte: key, byte: networkinfo.index, ulong: networkkey = 0
        args = b"00000000000000000000"
        msg = self.ID + args + self.mac
        checksum = self.calculate_checksum(msg)
        return MESSAGE_HEADER + msg + checksum + MESSAGE_FOOTER


class NodeAddRequest(NodeRequest):
    """
    Inform node it is added to the Plugwise Network it to memory of Circle+ node

    Response message: [acknowledge message]
    """

    ID = b"0007"

    def __init__(self, mac, accept: bool):
        super().__init__(mac)
        accept_value = 1 if accept == True else 0
        self.args.append(Int(accept_value, length=2))

    # This message has an exceptional format (MAC at end of message)
    # and therefore a need to override the serialize method
    def serialize(self):
        args = b"".join(a.serialize() for a in self.args)
        msg = self.ID + args + self.mac
        checksum = self.calculate_checksum(msg)
        return MESSAGE_HEADER + msg + checksum + MESSAGE_FOOTER


class NodeAllowJoiningRequest(NodeRequest):
    """
    Enable or disable receiving joining request of unjoined nodes

    Response message: ???
    """

    ID = b"0008"

    def __init__(self, accept: bool):
        super().__init__("")
        # TODO: Make sure that '01' means enable, and '00' disable joining
        val = 1 if accept == True else 0
        self.args.append(Int(val, length=2))


class NodeResetRequest(NodeRequest):
    """
    TODO: Some kind of reset request

    Response message: ???
    """

    ID = b"0009"

    def __init__(self, mac, moduletype, timeout):
        super().__init__(mac)
        self.args += [
            Int(moduletype, length=2),
            Int(timeout, length=2),
        ]


class StickInitRequest(NodeRequest):
    """
    initialize USB-Stick

    Response message: StickInitResponse
    """

    ID = b"000A"

    def __init__(self):
        """message for that initializes the Stick"""
        # init is the only request message that doesn't send MAC address
        super().__init__("")


class NodePingRequest(NodeRequest):
    """
    Ping node

    Response message: NodePingResponse
    """

    ID = b"000D"


class CirclePowerUsageRequest(NodeRequest):
    """
    Request current power usage

    Response message: CirclePowerUsageResponse
    """

    ID = b"0012"


class CircleClockSetRequest(NodeRequest):
    """
    Set internal clock of node

    Response message: [Acknowledge message]
    """

    ID = b"0016"

    def __init__(self, mac, dt):
        super().__init__(mac)
        passed_days = dt.day - 1
        month_minutes = (passed_days * 24 * 60) + (dt.hour * 60) + dt.minute
        d = DateTime(dt.year, dt.month, month_minutes)
        t = Time(dt.hour, dt.minute, dt.second)
        day_of_week = Int(dt.weekday(), 2)
        # FIXME: use LogAddr instead
        log_buf_addr = String("FFFFFFFF", 8)
        self.args += [d, log_buf_addr, t, day_of_week]


class CircleSwitchRelayRequest(NodeRequest):
    """
    switches relay on/off

    Response message: CircleSwitchRelayResponse
    """

    ID = b"0017"

    def __init__(self, mac, on):
        super().__init__(mac)
        val = 1 if on == True else 0
        self.args.append(Int(val, length=2))


class CirclePlusScanRequest(NodeRequest):
    """
    Get all linked Circle plugs from Circle+
    a Plugwise network can have 64 devices the node ID value has a range from 0 to 63

    Response message: CirclePlusScanResponse
    """

    ID = b"0018"

    def __init__(self, mac, node_address):
        super().__init__(mac)
        self.args.append(Int(node_address, length=2))
        self.node_address = node_address


class NodeRemoveRequest(NodeRequest):
    """
    Request node to be removed from Plugwise network by
    removing it from memory of Circle+ node.

    Response message: NodeRemoveResponse
    """

    ID = b"001C"

    def __init__(self, mac_circle_plus, mac_to_unjoined):
        super().__init__(mac_circle_plus)
        self.args.append(String(mac_to_unjoined, length=16))


class NodeInfoRequest(NodeRequest):
    """
    Request status info of node

    Response message: NodeInfoResponse
    """

    ID = b"0023"


class CircleCalibrationRequest(NodeRequest):
    """
    Request power calibration settings of node

    Response message: CircleCalibrationResponse
    """

    ID = b"0026"


class CirclePlusRealTimeClockSetRequest(NodeRequest):
    """
    Set real time clock of CirclePlus

    Response message: [Acknowledge message]
    """

    ID = b"0028"

    def __init__(self, mac, dt):
        super().__init__(mac)
        t = RealClockTime(dt.hour, dt.minute, dt.second)
        day_of_week = Int(dt.weekday(), 2)
        d = RealClockDate(dt.day, dt.month, dt.year)
        self.args += [t, day_of_week, d]


class CirclePlusRealTimeClockGetRequest(NodeRequest):
    """
    Request current real time clock of CirclePlus

    Response message: CirclePlusRealTimeClockResponse
    """

    ID = b"0029"


class CircleClockGetRequest(NodeRequest):
    """
    Request current internal clock of node

    Response message: CircleClockResponse
    """

    ID = b"003E"


class CirclePowerBufferRequest(NodeRequest):
    """
    Request power usage storaged a given memory address

    Response message: CirclePowerBufferResponse
    """

    ID = b"0048"

    def __init__(self, mac, log_address):
        super().__init__(mac)
        self.args.append(LogAddr(log_address, 8))


class NodeSleepConfigRequest(NodeRequest):
    """
    Configure timers for SED nodes to minimize battery usage

    Response message: Ack message with: ACK_SLEEP_SET
    """

    ID = b"0050"

    def __init__(self, mac, wake_up_duration: int, sleep: int, wake_up_interval: int):
        super().__init__(mac)

        # Interval in minutes a SED will get awake
        wake_up_interval_val = Int(wake_up_interval, length=4)
        # Duration in seconds the SED will be awake for receiving (n)acks
        wake_up_duration_val = Int(wake_up_duration, length=2)
        # Duration in seconds the node keeps sleeping
        sleep_val = Int(sleep, length=4)
        # TODO: Unknown parameter
        unknown_value = Int(0, length=6)
        self.args += [
            wake_up_duration_val,
            sleep_val,
            wake_up_interval_val,
            unknown_value,
        ]


class NodeSwitchGroupRequest(NodeRequest):
    """
    TODO:

    Response message: ????
    """

    ID = b"0055"


class PlugwiseClearGroupMacRequest(NodeRequest):
    """
    TODO:

    Response message: ????
    """

    ID = b"0058"

    def __init__(self, mac, taskId):
        super().__init__(mac)
        self.args.append(Int(taskId, length=2))


class NodeFeaturesRequest(NodeRequest):
    """
    Request feature set node supports

    Response message: NodeFeaturesResponse
    """

    ID = b"005F"


class ScanConfigRequest(NodeRequest):
    """
    Configure a Scan node

    reset_timer : Delay in minutes when signal is send when no motion is detected
    sensitivity : Sensitivity of Motion sensor (High, Medium, Off)
    light       : Daylight override to only report motion when lightlevel is below calibrated level

    Response message: [Acknowledge message]
    """

    ID = b"0101"

    def __init__(self, mac, reset_timer: int, sensitivity: int, light: bool):
        super().__init__(mac)

        reset_timer_value = Int(reset_timer, length=2)
        # Sensitivity: HIGH(0x14),  MEDIUM(0x1E),  OFF(0xFF)
        sensitivity_value = Int(sensitivity, length=2)
        light_temp = 1 if light == True else 0
        light_value = Int(light_temp, length=2)
        self.args += [
            sensitivity_value,
            light_value,
            reset_timer_value,
        ]


class ScanLightCalibrateRequest(NodeRequest):
    """
    Calibrate light sensitivity

    Response message: [Acknowledge message]
    """

    ID = b"0102"
