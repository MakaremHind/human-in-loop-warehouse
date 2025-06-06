import json
import time
import uuid
import paho.mqtt.client as mqtt

BROKER = "192.168.50.100"#"localhost"
PORT = 1883
TOPIC = "base_01/order_request"






def generate_order():
    return {"header":{"timestamp":1747839147.311,"sender_id":"OrderGenerator","correlation_id":"Lapu"},"starting_module":{"namespace":"conveyor_02","pose":{"x":323.5946044921875,"y":130.4923095703125,"z":58,"roll":0,"pitch":0,"yaw":0}},"goal":{"namespace":"container_02","pose":{"x":367.49945068359375,"y":500.1705627441406,"z":130,"roll":0,"pitch":0,"yaw":0}},"cargo_box":{"id":1,"color":"red","type":"small","global_pose":{"x":0,"y":0,"z":0,"roll":0,"pitch":0,"yaw":0}}}


def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    print("[Order Generator] Starting loop...")
   
    order = generate_order()
    client.publish(TOPIC, json.dumps(order), qos=1)
    client.loop(2)  # Allow time for message to be sent
    print("Published mock order to", TOPIC)
    

if __name__ == "__main__":
    main()
