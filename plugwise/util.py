"""
Use of this source code is governed by the MIT license found in the LICENSE file.

Plugwise protocol helpers
"""
import binascii
import crcmod
import datetime
import logging
import re
import struct
import sys
from .exceptions import *
from .constants import *


crc_fun = crcmod.mkCrcFun(0x11021, rev=False, initCrc=0x0000, xorOut=0x0000)

def validate_mac(mac):
    if not re.match("^[A-F0-9]+$", mac):
        return False

    try:
        _ = int(mac, 16)
    except ValueError:
        return False

    return True

def inc_seq_id(seq_id, value=1):
    """
    Increment sequence id by 1

    :return: 4 bytes
    """
    temp = str(hex(int(seq_id, 16) + value)).lstrip("0x").upper()
    while len(temp) < 4:
        temp = "0" + temp
    return temp.encode()

class PlugwiseException(Exception):
    """Plugwise Exception."""

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class BaseType(object):
    def __init__(self, value, length):
        self.value = value
        self.length = length

    def serialize(self):
        return bytes(self.value, 'utf-8')

    def unserialize(self, val):
        self.value = val

    def __len__(self):
        return self.length

class CompositeType(BaseType):
    def __init__(self):
        self.contents = []

    def serialize(self):
        return b''.join(a.serialize() for a in self.contents)

    def unserialize(self, val):
        for p in self.contents:
            myval = val[:len(p)]
            p.unserialize(myval)
            val = val[len(myval):]
        return val
        
    def __len__(self):
        return sum(len(x) for x in self.contents)

class String(BaseType):
    pass

class Int(BaseType):
    def __init__(self, value, length=2):
        self.value = value
        self.length = length

    def serialize(self):
        fmt = "%%0%dX" % self.length
        return bytes(fmt % self.value, 'utf-8')

    def unserialize(self, val):
        self.value = int(val, 16)

class UnixTimestamp(Int):
    def __init__(self, value, length=8):
        Int.__init__(self, value, length=length)

    def unserialize(self, val):
        Int.unserialize(self, val)
        self.value = datetime.datetime.fromtimestamp(self.value)

class Year2k(Int):
    """year value that is offset from the year 2000"""

    def unserialize(self, val):
        Int.unserialize(self, val)
        self.value += PLUGWISE_EPOCH

class DateTime(CompositeType):
    """datetime value as used in the general info response
    format is: YYMMmmmm
    where year is offset value from the epoch which is Y2K
    and last four bytes are offset from the beginning of the month in minutes
    """

    def __init__(self, year=0, month=0, minutes=0):
        CompositeType.__init__(self)        
        self.year = Year2k(year-PLUGWISE_EPOCH, 2)
        self.month = Int(month, 2)
        self.minutes = Int(minutes, 4)
        self.contents += [self.year, self.month, self.minutes]

    def unserialize(self, val):
        CompositeType.unserialize(self, val)
        minutes = self.minutes.value
        hours = minutes // 60
        days = hours // 24
        hours -= (days*24)
        minutes -= (days*24*60)+(hours*60)
        try:
            self.value = datetime.datetime(self.year.value, self.month.value, days+1, hours, minutes)
        except ValueError:
            debug('encountered value error while attempting to construct datetime object')
            self.value = None

class Time(CompositeType):
    """time value as used in the clock info response"""

    def __init__(self, hour=0, minute=0, second=0):
        CompositeType.__init__(self)
        self.hour = Int(hour, 2)
        self.minute = Int(minute, 2)
        self.second = Int(second, 2)
        self.contents += [self.hour, self.minute, self.second]

    def unserialize(self, val):
        CompositeType.unserialize(self, val)
        self.value = datetime.time(self.hour.value, self.minute.value, self.second.value)
        
class Float(BaseType):
    def __init__(self, value, length=4):
        self.value = value
        self.length = length

    def unserialize(self, val):
        hexval = binascii.unhexlify(val)
        self.value = struct.unpack("!f", hexval)[0]

class LogAddr(Int):
    LOGADDR_OFFSET = 278528

    def serialize(self):
        return bytes("%08X" % ((self.value * 32) + self.LOGADDR_OFFSET), 'utf-8')

    def unserialize(self, val):
        Int.unserialize(self, val)
        self.value = (self.value - self.LOGADDR_OFFSET) // 32
