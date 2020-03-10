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
            print ("- state : " + str(plugwise.node(mac).available))
            print ("- update: " + str(plugwise.node(mac).get_last_update()))
            print ("- hw ver: " + str(plugwise.node(mac).get_hardware_version()))
            print ("- fw ver: " + str(plugwise.node(mac).get_firmware_version()))
            print ("- relay : " + str(plugwise.node(mac).is_on()))
            print ("")
        print ("circle+ = " + plugwise.nodes()[0])
        node = plugwise.node(plugwise.nodes()[0])
        mac = node.get_mac()
        print("Register callback for power use updates of node " + mac)
        node.on_status_update(power_update, CALLBACK_POWER)

        print("start auto update every 10 sec")
        plugwise.auto_update(10)

    plugwise.scan(scan_finished, True)

## Main ##
print("start connecting to stick")
port = "com5" #"/dev/ttyUSB0"  # or "com1" at Windows
plugwise = plugwise.stick(port, scan_start)

time.sleep(300)
print("stop auto update")
plugwise.auto_update(0)

time.sleep(5)

print("Exiting ...")
plugwise.stop()

