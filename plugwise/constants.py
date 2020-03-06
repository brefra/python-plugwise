
# Serial connection settings for plugwise USB stick
BAUD_RATE = 115200
BYTE_SIZE = 8
PARITY = "N"
STOPBITS = 1

# Node types
NODE_TYPE_STICK = 0
NODE_TYPE_CIRCLE_PLUS = 1
NODE_TYPE_CIRCLE = 2
NODE_TYPE_SWITCH = 3
NODE_TYPE_SENSE = 5
NODE_TYPE_SCAN = 6
NODE_TYPE_STEALTH = 9

# Plugwise message identifiers
MESSAGE_FOOTER = b'\x0d\x0a'
MESSAGE_HEADER = b'\x05\x05\x03\x03'

# Max timeout in seconds
MESSAGE_TIME_OUT = 10
MESSAGE_RETRY = 2

# plugwise year information is offset from y2k
PLUGWISE_EPOCH = 2000
PULSES_PER_KW_SECOND = 468.9385193

# Default sleep between sending messages
SLEEP_TIME = 150 / 1000

# Callback types
CALLBACK_RELAY = "RELAY"
CALLBACK_POWER = "POWER"

# Home Assistant entities
HA_SWITCH = "switch"
HA_SENSOR = "sensor"
