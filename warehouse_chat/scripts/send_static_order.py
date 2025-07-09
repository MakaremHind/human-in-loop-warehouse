# send_static_order.py
import json
import time
import uuid
import paho.mqtt.client as mqtt

# ------------------------------------------------------------------
# 1) SETTINGS — change these if necessary
# ------------------------------------------------------------------
BROKER = "192.168.50.100"        # your MQTT broker IP / hostname
PORT   = 1883                    # default MQTT port
TOPIC  = "base_01/order_request" # topic the master listens on
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 2) STATIC PAYLOAD — adjust to your needs
# ------------------------------------------------------------------
correlation_id = str(uuid.uuid4())   # unique ID for this order
payload = {"header": {"timestamp": 1750247342.9206116, "sender_id": "OrderGenerator", "correlation_id": "04dc09fa-d3b9-46dc-8f6b-6602a1c9dc7d"}, 
           "starting_module": {"namespace": "container_01", "pose": {"x": 211.0592803955078, "y": 299.2781066894531, "z": 130.0, "roll": 0.0, "pitch": 0.0, "yaw": -3.141592653589793}},
           "goal": {"namespace": "container_02", "pose": {"x": 227.8921661376953, "y": 498.0125732421875, "z": 130.0, "roll": 0.0, "pitch": 0.0, "yaw": -3.141592653589793}}, 
           "cargo_box": {"id": 7, "color": "red", "type": "small", "global_pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}}}
# ------------------------------------------------------------------


print(f"Publishing order {correlation_id} to {BROKER}:{PORT} topic '{TOPIC}'")

client = mqtt.Client()
client.connect(BROKER, PORT)
client.publish(TOPIC, json.dumps(payload))
client.disconnect()

print("✅  Static order sent.")

