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
)


class PlugwiseRequest(PlugwiseMessage):
    def __init__(self, mac):
        PlugwiseMessage.__init__(self)
        self.args = []
        self.mac = mac


class StickInitRequest(PlugwiseRequest):
    """initialize Stick"""

    ID = b"000A"

    def __init__(self):
        """message for that initializes the Stick"""
        # init is the only request message that doesn't send MAC address
        PlugwiseRequest.__init__(self, "")


class CircleScanRequest(PlugwiseRequest):
    """
    Get all linked Circle plugs from Circle+
    a Plugwise network can have 64 devices the node ID value has a range from 0 to 63    
    """
    ID = b'0018'

    def __init__(self, mac, node_id):
        PlugwiseRequest.__init__(self, mac)
        self.args.append(Int(node_id, length=2))


class PlugPowerUsageRequest(PlugwiseRequest):
    ID = b"0012"


class PlugInfoRequest(PlugwiseRequest):
    ID = b"0023"


class PlugwiseClockInfoRequest(PlugwiseRequest):
    ID = b"003E"


class PlugwiseClockSetRequest(PlugwiseRequest):
    ID = b"0016"

    def __init__(self, mac, dt):
        PlugwiseRequest.__init__(self, mac)
        passed_days = dt.day - 1
        month_minutes = (passed_days * 24 * 60) + (dt.hour * 60) + dt.minute
        d = DateTime(dt.year, dt.month, month_minutes)
        t = Time(dt.hour, dt.minute, dt.second)
        day_of_week = Int(dt.weekday(), 2)
        # FIXME: use LogAddr instead
        log_buf_addr = String("FFFFFFFF", 8)
        self.args += [d, log_buf_addr, t, day_of_week]


class PlugSwitchRequest(PlugwiseRequest):
    """switches Plug or or off"""

    ID = b"0017"

    def __init__(self, mac, on):
        PlugwiseRequest.__init__(self, mac)
        val = 1 if on == True else 0
        self.args.append(Int(val, length=2))


class PlugCalibrationRequest(PlugwiseRequest):
    ID = b"0026"


class PlugwisePowerBufferRequest(PlugwiseRequest):
    ID = b"0048"

    def __init__(self, mac, log_address):
        PlugwiseRequest.__init__(self, mac)
        self.args.append(LogAddr(log_address, 8))
