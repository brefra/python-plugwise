
# Serial connection settings for plugwise USB stick
BAUD_RATE = 115200
BYTE_SIZE = 8
PARITY = "N"
STOPBITS = 1

# Plugwise message identifiers
MESSAGE_FOOTER = b'\x0d\x0a'
MESSAGE_HEADER = b'\x05\x05\x03\x03'

# Acknowledge message types
ACK_NOT_EXTENDED = 0
ACK_SENSE_INTERVAL_SET = 179
NACK_SENSE_INTERVAL_SET = 180
ACK_SENSE_BOUNDARIES_SET = 181
NACK_SENSE_BOUNDARIES_SET = 182
ACK_LIGHT_CALIBRATION = 189
ACK_SCAN_PARAMETERS_SET = 190
NACK_SCAN_PARAMETERS_SET = 191
ACK_SUCCESS = 193
ACK_ERROR = 194
ACK_CIRCLE_PLUS = 221
ACK_CLOCK_SET = 215
ACK_ON = 216
ACK_POWER_CALIBRATION = 218
ACK_OFF = 222
ACK_REAL_TIME_CLOCK_SET = 223
ACK_TIMEOUT = 225
NACK_ON_OFF = 226
NACK_REAL_TIME_CLOCK_SET = 231
ACK_SLEEP_SET = 246
ACK_POWER_LOG_INTERVAL_SET = 248

# Max timeout in seconds
MESSAGE_TIME_OUT = 5
MESSAGE_RETRY = 2

# plugwise year information is offset from y2k
PLUGWISE_EPOCH = 2000
PULSES_PER_KW_SECOND = 468.9385193
LOGADDR_OFFSET = 278528

# Default sleep between sending messages
SLEEP_TIME = 150 / 1000

# Max seconds the internal clock of plugwise nodes
# are allowed to drift in seconds
MAX_TIME_DRIFT = 30

# Default sleep time in seconds for watchdog deamon
WATCHDOG_DEAMON = 60

# Automatically accept new join requests
ACCEPT_JOIN_REQUESTS = False

# Node types
NODE_TYPE_STICK = 0
NODE_TYPE_CIRCLE_PLUS = 1   #AME_NC
NODE_TYPE_CIRCLE = 2        #AME_NR
NODE_TYPE_SWITCH = 3        #AME_SEDSwitch
NODE_TYPE_SENSE = 5         #AME_SEDSense
NODE_TYPE_SCAN = 6          #AME_SEDScan
NODE_TYPE_CELSIUS_SED = 7   #AME_CelsiusSED
NODE_TYPE_CELSIUS_NR = 8    #AME_CelsiusNR
NODE_TYPE_STEALTH = 9       #AME_STEALTH_ZE
# 10 AME_MSPBOOTLOAD
# 11 AME_STAR

# Defaults for SED's (Sleeping End Devices)
SED_STAY_ACTIVE = 10            # Time in seconds the SED keep itself awake to receive and respond to other messages
SED_SLEEP_FOR = 60              # Time in minutes the SED will sleep
SED_MAINTENANCE_INTERVAL = 1440 # 24 hours, Interval in minutes the SED will get awake and notify it's available for maintenance purposes
SED_CLOCK_SYNC = True           # Enable or disable synchronizing clock
SED_CLOCK_INTERVAL = 25200      # 7 days, duration in minutes the node synchronize its clock


# Scan motion Sensitivity levels
SCAN_SENSITIVITY_HIGH = "high"
SCAN_SENSITIVITY_MEDIUM = "medium"
SCAN_SENSITIVITY_OFF = "medium"

# Defaults for Scan Devices
SCAN_MOTION_RESET_TIMER = 5                 # Time in minutes the motion sensor should not sense motion to report "no motion" state
SCAN_SENSITIVITY = SCAN_SENSITIVITY_MEDIUM  # Default sensitivity of the motion sensors
SCAN_DAYLIGHT_MODE = False                  # Light override 

# Sense calculations
SENSE_HUMIDITY_MULTIPLIER = 125
SENSE_HUMIDITY_OFFSET = 6
SENSE_TEMPERATURE_MULTIPLIER = 175.72
SENSE_TEMPERATURE_OFFSET = 46.85

# Callback types
CB_NEW_NODE = "NEW_NODE"
CB_JOIN_REQUEST = "JOIN_REQUEST"

# Unit of measurement
TIME_MILLISECONDS = "ms"
POWER_WATT = "W"
ENERGY_KILO_WATT_HOUR = "kWh"
ENERGY_WATT_HOUR = "Wh"
CELSIUS = "°C"

# Sensors
SENSOR_AVAILABLE = {
    "id": "available",
    "name": "Available",
    "state": "get_available",
    "unit": "state",
}
SENSOR_HUMIDITY = {
    "id": "humidity",
    "name": "Humidity",
    "state": "get_humidity",
    "unit": "%"
}
SENSOR_MOTION = {
    "id": "motion",
    "name": "Motion",
    "state": "get_motion",
    "unit": "state"
}
SENSOR_PING = {
    "id": "ping",
    "name": "Ping roundtrip",
    "state": "get_ping",
    "unit": TIME_MILLISECONDS,
}
SENSOR_POWER_USE = {
    "id": "power_1s",
    "name": "Power usage",
    "state": "get_power_usage",
    "unit": POWER_WATT,
}
SENSOR_POWER_USE_LAST_8_SEC = {
    "id": "power_8s",
    "name": "Power usage 8 seconds",
    "state": "get_power_usage_8_sec",
    "unit": POWER_WATT,
}
SENSOR_POWER_CONSUMPTION_CURRENT_HOUR = {
    "id": "power_con_cur_hour",
    "name": "Power consumption current hour",
    "state": "get_power_consumption_current_hour",
    "unit": ENERGY_KILO_WATT_HOUR,
}
SENSOR_POWER_CONSUMPTION_PREVIOUS_HOUR = {
    "id": "power_con_prev_hour",
    "name": "Power consumption previous hour",
    "state": "get_power_consumption_previous_hour",
    "unit": ENERGY_KILO_WATT_HOUR,
}
SENSOR_POWER_CONSUMPTION_TODAY = {
    "id": "power_con_today",
    "name": "Power consumption today",
    "state": "get_power_consumption_today",
    "unit": ENERGY_KILO_WATT_HOUR, 
}
SENSOR_POWER_CONSUMPTION_YESTERDAY = {
    "id": "power_con_yesterday",
    "name": "Power consumption yesterday",
    "state": "get_power_consumption_yesterday",
    "unit": ENERGY_KILO_WATT_HOUR, 
}
SENSOR_POWER_PRODUCTION_CURRENT_HOUR = {
    "id": "power_prod_cur_hour",
    "name": "Power production current hour",
    "state": "get_power_production_current_hour",
    "unit": ENERGY_KILO_WATT_HOUR, 
}
SENSOR_POWER_PRODUCTION_PREVIOUS_HOUR = {
    "id": "power_prod_prev_hour",
    "name": "Power production previous hour",
    "state": "get_power_production_previous_hour",
    "unit": ENERGY_KILO_WATT_HOUR, 
}
SENSOR_SWITCH = {
    "id": "switch",
    "name": "switch",
    "state": "get_switch_state",
    "unit": "state",
}
SENSOR_TEMPERATURE = {
    "id": "temperature",
    "name": "Temperature",
    "state": "get_temperature",
    "unit": CELSIUS,
}

# TODO: Need to validate RSSI sensors
SENSOR_RSSI_IN = {
    "id": "RSSI_in",
    "name": "RSSI in",
    "state": "get_rssi_in",
    "unit": "Unknown",
}
SENSOR_RSSI_OUT = {
    "id": "RSSI_out",
    "name": "RSSI out",
    "state": "get_rssi_out",
    "unit": "Unknown",
}

# Switches
SWITCH_RELAY = {
    "id": "relay",
    "name": "Relay state",
    "state": "get_relay_state",
    "switch": "set_relay_state",
}

# Home Assistant entities
HA_SWITCH = "switch"
HA_SENSOR = "sensor"
HA_BINARY_SENSOR = "binary_sensor"
