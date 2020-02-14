
# serial connection settings for plugwise USB stick
BAUD_RATE = 115200
BYTE_SIZE = 8
PARITY = "N"
STOPBITS = 1

# Plugwise message identifiers
MESSAGE_FOOTER = b'\x0d\x0a'
MESSAGE_HEADER = b'\x05\x05\x03\x03'

# plugwise year information is offset from y2k
PLUGWISE_EPOCH = 2000
PULSES_PER_KW_SECOND = 468.9385193

# Default sleep between sending messages
SLEEP_TIME = 250 / 1000

# Callback types
CALLBACK_RELAY = "RELAY"
CALLBACK_POWER = "POWER"
