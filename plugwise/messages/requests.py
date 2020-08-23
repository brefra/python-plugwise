"""
Use of this source code is governed by the MIT license found in the LICENSE file.

All (known) request messages to be send to plugwise plugs
"""
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
    def __init__(self, mac):
        PlugwiseMessage.__init__(self)
        self.args = []
        self.mac = mac


class CirclePowerUsageRequest(NodeRequest):
    """Request current power usage"""

    ID = b"0012"


class CircleSwitchRequest(NodeRequest):
    """switches relay on/off"""

    ID = b"0017"

    def __init__(self, mac, on):
        super().__init__(mac)
        val = 1 if on == True else 0
        self.args.append(Int(val, length=2))


class CircleCalibrationRequest(NodeRequest):
    """Request power calibration settings"""

    ID = b"0026"


class CirclePowerBufferRequest(NodeRequest):
    """Request collected power usage"""

    ID = b"0048"

    def __init__(self, mac, log_address):
        super().__init__(mac)
        self.args.append(LogAddr(log_address, 8))


class CirclePlusRealTimeClockSetRequest(NodeRequest):
    """Set real time clock of CirclePlus"""

    ID = b"0028"

    def __init__(self, mac, dt):
        super().__init__(mac)
        t = RealClockTime(dt.hour, dt.minute, dt.second)
        day_of_week = Int(dt.weekday(), 2)
        d = RealClockDate(dt.day, dt.month, dt.year)
        self.args += [t, day_of_week, d]


class CirclePlusRealTimeClockGetRequest(NodeRequest):
    """Request current real time clock of CirclePlus"""

    ID = b"0029"


class CirclePlusScanRequest(NodeRequest):
    """
    Get all linked Circle plugs from Circle+
    a Plugwise network can have 64 devices the node ID value has a range from 0 to 63    
    """

    ID = b"0018"

    def __init__(self, mac, node_address):
        super().__init__(mac)
        self.args.append(Int(node_address, length=2))
        self.node_address = node_address


class NodeClockGetRequest(NodeRequest):
    """Request clock of node"""

    ID = b"003E"


class NodeClockSetRequest(NodeRequest):
    """Set clock of node"""

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


class SEDSleepConfigRequest(NodeRequest):
    """Configure timers for SED nodes (battery powered)"""

    ID = b"0050"

    def __init__(self, mac, wake_up_duration : int, sleep : int, wake_up_interval : int):
        super().__init__(mac)

        # Interval to awake (to report its availability ??
        wake_up_interval_val = Int(wake_up_interval, length=4)
        # Duration the node keeps awake (for receiving (n)acks ??)
        wake_up_duration_val = Int(wake_up_duration, length=2)
        # Duration the node keeps sleeping
        sleep_val = Int(sleep, length=4)
        # TODO: Unkown parameter
        unknown_value = Int(0, length=6)
        self.args += [
            wake_up_duration_val,
            sleep_val,
            wake_up_interval_val,
            unknown_value,
        ]


class NodeSwitchGroupRequest(NodeRequest):
    """ TODO:  """

    ID = b"0055"


class ScanConfigRequest(NodeRequest):
    """Configure a Scan node"""

    ID = b"0101"

    def __init__(self, mac, reset_timer: int, sensitivity : int, light : bool):
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
    """Calibrate light sensitivity"""

    ID = b"0102"


class NodePingRequest(NodeRequest):
    """Ping node"""

    ID = b"000D"


class NodeInfoRequest(NodeRequest):
    """Request status info of node"""

    ID = b"0023"


class NodeJoinAcceptRequest(NodeRequest):
    """Request Node to join by accepting join request"""

    ID = b"0007"

    def __init__(self, mac, accept: bool):
        super().__init__(mac)
        accept_value = 1 if accept == True else 0
        self.args.append(Int(accept_value, length=2))


class StickInitRequest(NodeRequest):
    """initialize Stick"""

    ID = b"000A"

    def __init__(self):
        """message for that initializes the Stick"""
        # init is the only request message that doesn't send MAC address
        super().__init__("")
