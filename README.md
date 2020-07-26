# python-plugwise: An async python library to control Plugwise plugs Circle+ and Circle

This library was created to extent my [Home Assisstant](https://home-assistant.io) setup with the [Plugwise](https://plugwise.com) legacy USB-stick to control the linked Circle+ and [Circle](https://www.plugwise.com/en_US/products/circle) plugs which could be controlled by the legacy Windows [Source application](https://www.plugwise.com/en_US/source) supplied by Plugwise.
As the primary goal is to support Plugwise nodes in Home Assistant, it can also be used independently.

Be aware this library does NOT support the new [Plug](https://www.plugwise.com/en_US/products/plug) (identified by having a local button) which complies to the [Zigbee](https://zigbeealliance.org/) standard, while this is not the case for the legacy plugwise devices.

There's no official documentation available about the protocol of the Plugwise so this library is based on partial reverse engineering by [Maarten Damen](https://maartendamen.com/category/plugwise-unleashed/)
and several other sources [bitbucket.org/hadara/python-plugwise](https://bitbucket.org/hadara/python-plugwise/wiki/Home) and [openHAB](https://github.com/openhab/openhab-addons)

The latest version of the library is published as a python package on [pypi](https://pypi.python.org/pypi/python-plugwise) and currently supports the devices and functions listed below:

| Plugwise node | Relay control | Power monitoring | Comments |
| ----------- | ----------- | ----------- | ----------- |
| Circle+ | Yes | Yes | Working |
| Circle | Yes | Yes | Working |
| Scan | No | No | Not supported yet |
| Sense | No | No | Not supported yet |
| Switch | No | No | Not supported yet |
| Stealth | Yes | Yes | Experimental (not tested) |
| Sting | No | No | Not supported yet |

When the connection to the stick is initialized it will automatically do a discovery of all linked nodes.

I would like to extend this library to support other Plugwise device types, unfortunately I do not own these devices so I'm unable to test. So feel free to submit pull requests or log issues through [github](https://github.com/brefra/python-plugwise) for functionality you like to have included.

Note: This library does not support linking or removing nodes from the Plugwise network (yet). You still need the Plugwise Source software for that.

## Install

To install this library use the following command:
```
pip install python-plugwise
```

## Example usage

The library currently only supports a USB (serial) connection (socket connection is in development) to the Plugwise stick. In order to use the library, you need to first initialize the stick and trigger a scan to query the Circle+ for all linked nodes in the Plugwise Zigbee network.

```python

import plugwise
from plugwise.constants import SENSOR_POWER_USE

def scan_finished():
    """
    Callback for init finished
    """

    def power_update(power_use):
        """
        Callback for new power use value
        """
        print("New power use value : " + str(round(power_use, 2)))


    print("== Initialization has finished ==")
    print("")
    for mac in plugwise.nodes():
        print ("- type  : " + str(plugwise.node(mac).get_node_type()))
        print ("- mac   : " + mac)
        print ("- state : " + str(plugwise.node(mac).get_available()))
        print ("- update: " + str(plugwise.node(mac).get_last_update()))
        print ("- hw ver: " + str(plugwise.node(mac).get_hardware_version()))
        print ("- fw ver: " + str(plugwise.node(mac).get_firmware_version()))
        print ("- relay : " + str(plugwise.node(mac).get_relay_state()))
        print ("")
    print ("circle+ = " + plugwise.nodes()[0])
    node = plugwise.node(plugwise.nodes()[0])
    mac = node.get_mac()
    print("Register callback for power use updates of node " + mac)
    node.subscribe_callback(power_update, SENSOR_POWER_USE["state"])

    print("start auto update every 10 sec")
    plugwise.auto_update(10)
    time.sleep(5)
    plugwise.node("000D6F00003FD440").set_relay_state(True)
    time.sleep(5)
    plugwise.node("000D6F00003FD440").set_relay_state(False)

    time.sleep(5)
    print ("Circle+ Poweruse last second (W)             : " + str(node.get_power_usage()))
    print ("Circle+ Poweruse last 8 seconds (W)          : " + str(node.get_power_usage_8_sec()))
    print ("Circle+ Power consumption current hour (kWh) : " + str(node.get_power_consumption_current_hour()))
    print ("Circle+ Power consumption previous hour (kWh): " + str(node.get_power_consumption_previous_hour()))
    print ("Circle+ Power consumption today (kWh)        : " + str(node.get_power_consumption_today()))
    print ("Circle+ Power consumption yesterday (kWh)    : " + str(node.get_power_consumption_yesterday()))
    print ("Circle+ Power production previous hour (kWh) : " + str(node.get_power_production_current_hour()))
    print ("Circle+ Power production current hour (kWh)  : " + str(node.get_power_production_previous_hour()))
    print ("Circle+ Ping roundtrip (ms)                  : " + str(node.get_ping()))
    print ("Circle+ RSSI in                              : " + str(node.get_rssi_in()))
    print ("Circle+ RSSI out                             : " + str(node.get_rssi_out()))


## Main ##
port = "/dev/ttyUSB0"  # or "com1" at Windows
plugwise = plugwise.stick(port, scan_finished, True)

time.sleep(300)
print("stop auto update")
plugwise.auto_update(0)

time.sleep(5)

print("Exiting ...")
plugwise.disconnect()
```

## Usage

You can use example.py as an example to get power usage from the Circle+
