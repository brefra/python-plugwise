"""
Example to connect to a Plugwise stick and controle plugwise nodes

"""
import time
import sys
sys.path.append("..")
import plugwise

# Callback types
CALLBACK_RELAY = "RELAY"
CALLBACK_POWER = "POWER"

def scan_start():
    print("start scan for Plugwise nodes (takes 1 minute)")
    plugwise.scan(scan_finished)

def scan_finished():
    """
    Callback for init finished
    """
    print("== Initialization has finished ==")
    print("")
    for mac in plugwise.nodes():
        print ("= " + mac + " =")
        print ("- type  : " + str(plugwise.node(mac).get_node_type()))
        print ("- state : " + str(plugwise.node(mac).available))
        print ("- update: " + str(plugwise.node(mac).get_last_update()))
        print ("- hw ver: " + str(plugwise.node(mac).get_hardware_version()))
        print ("- fw ver: " + str(plugwise.node(mac).get_firmware_version()))
        print ("- relay : " + str(plugwise.node(mac).is_on()))
        print ("")
    
    def power_update(power_use):
        print("New power use value : " + str(power_use))

    print ("circle+ = " + plugwise.nodes()[-1])
    node = plugwise.node(plugwise.nodes()[-1])
    mac = node.get_mac()
    print("Register callback for power use updates of node " + mac)
    node.on_status_update(CALLBACK_POWER, power_update)

    print("start auto update")
    plugwise.auto_update()


## Main ##

print("start connecting to stick")
port = "com5"
plugwise = plugwise.stick(port, scan_start)

time.sleep(300)
print("stop auto update")
plugwise.auto_update(0)

time.sleep(5)

print("Exiting ...")
plugwise.stop()

