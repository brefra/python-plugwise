## python-plugwise: A python library to control Plugwise plugs Circle+ and Circle

This library was created to extent my [Home Assisstant](https://home-assistant.io) setup with the [Plugwise](https://plugwise.com) stick to control the linked Circle+ and [Circle](https://www.plugwise.com/en_US/products/circle) plugs.
As the primary goal is to support Plugwise nodes in Home Assistant, it can also be used independently.

There's no official documentation available about the protocol of the Plugwise so this library is based on partial reverse engineering by [Maarten Damen](https://maartendamen.com/category/plugwise-unleashed/)
and several other sources [bitbucket.org/hadara/python-plugwise](https://bitbucket.org/hadara/python-plugwise/wiki/Home) and [openHAB](https://github.com/openhab/openhab-addons)

The latest version of the library is published as a python package on [pypi](https://pypi.python.org/pypi/python-plugwise) and currently supports the devices an functions listed below:

| Plugwise node | Relay control | Power monitoring | Comments |
| ----------- | ----------- | ----------- | ----------- |
| Circle+ | Yes | Yes | Scan for linked nodes |
| Circle | Yes | Yes | |
| Scan | No | No | Not supported yet |
| Sense | No | No | Not supported yet |
| Switch | No | No | Not supported yet |
| Stealth | No | No | Not supported yet |
| Sting | No | No | Not supported yet |

I would like to extend this library to support other Plugwise device types, unfortunately I do not own these devices so I'm unable to test. So feel free to submit pull requests or log issues through [github](https://github.com/brefra/python-plugwise) for functionality you like to have included.

Note: This library does not support linking or removing nodes from the Plugwise network. You still need the Plugwise Source software for that.

# Install
To install run the following command as root:
```
python setup.py install
```

# Example usage

The library currently only supports a USB (serial) connection (socket connection is in development) to the Plugwise stick. In order to use the library, you need to first initialize the stick and trigger a scan to query the Circle+ for all linked nodes in the Plugwise Zigbee network.


```python
import plugwise

plugwise = plugwise.stick("/dev/ttyUSB0")
plugwise.scan(discovery_finished)

def discovery_finished():
    """
    Callback when discovery finished
    """
    print("")
    for mac in plugwise.nodes():
        print ("= " + mac + " =")
        print ("- Device type      : " + str(plugwise.node(mac).get_node_type()))
        print ("- Connection state : " + str(plugwise.node(mac).available))
        print ("- Last update      : " + str(plugwise.node(mac).get_last_update()))
        print ("- Hardware version : " + str(plugwise.node(mac).get_hardware_version()))
        print ("- Firmware version : " + str(plugwise.node(mac).get_firmware_version()))
        print ("- Relay state      : " + str(plugwise.node(mac).is_on()))
        print ("")

    def log_power_update(power_use):
        print("New power use value for Circle+ : " + str(power_use))

    print("Register callback for power use updates of Circle+")
    node = plugwise.node(plugwise.nodes()[-1])
    mac = node.get_mac()
    node.on_status_update("POWER", log_power_update)

    print("Start auto update")
    plugwise.auto_update(10)

    time.sleep(300)
```

# Usage
You can use example.py as an example to get power usage from the Circle+
