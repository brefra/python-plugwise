"""
Example to connect to a Plugwise stick and controle plugwise nodes

"""
import time
import sys

sys.path.append("..")
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
        print("- type  : " + str(plugwise.node(mac).get_node_type()))
        print("- mac   : " + mac)
        print("- state : " + str(plugwise.node(mac).get_available()))
        print("- update: " + str(plugwise.node(mac).get_last_update()))
        print("- hw ver: " + str(plugwise.node(mac).get_hardware_version()))
        print("- fw ver: " + str(plugwise.node(mac).get_firmware_version()))
        print("- relay : " + str(plugwise.node(mac).get_relay_state()))
        print("")
    print("circle+ = " + plugwise.nodes()[0])
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
    print(
        "Circle+ Poweruse last second (W)             : " + str(node.get_power_usage())
    )
    print(
        "Circle+ Poweruse last 8 seconds (W)          : "
        + str(node.get_power_usage_8_sec())
    )
    print(
        "Circle+ Power consumption current hour (kWh) : "
        + str(node.get_power_consumption_current_hour())
    )
    print(
        "Circle+ Power consumption previous hour (kWh): "
        + str(node.get_power_consumption_previous_hour())
    )
    print(
        "Circle+ Power consumption today (kWh)        : "
        + str(node.get_power_consumption_today())
    )
    print(
        "Circle+ Power consumption yesterday (kWh)    : "
        + str(node.get_power_consumption_yesterday())
    )
    print(
        "Circle+ Power production previous hour (kWh) : "
        + str(node.get_power_production_current_hour())
    )
    print(
        "Circle+ Power production current hour (kWh)  : "
        + str(node.get_power_production_previous_hour())
    )
    print("Circle+ Ping roundtrip (ms)                  : " + str(node.get_ping()))
    print("Circle+ RSSI in                              : " + str(node.get_rssi_in()))
    print("Circle+ RSSI out                             : " + str(node.get_rssi_out()))


## Main ##
port = "/dev/ttyUSB0"  # or "com1" at Windows
plugwise = plugwise.stick(port, scan_finished, True)

time.sleep(300)
print("stop auto update")
plugwise.auto_update(0)

time.sleep(5)

print("Exiting ...")
plugwise.disconnect()
