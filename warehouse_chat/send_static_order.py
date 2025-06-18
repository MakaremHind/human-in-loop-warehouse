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
payload = {
    "header": {
        "timestamp": time.time(),
        "sender_id": "StaticOrderScript",
        "correlation_id": correlation_id
    },
    "starting_module": {
        "namespace": "manual_pose_start",
        "pose": {"x": 301.8318176269531, "y": 283.3472595214844, "z": 15.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    },
    "goal":{"namespace":"container_01","pose":{"x":211.4357452392578,"y":298.7314453125,"z":130,"roll":0,"pitch":0,"yaw":-3.141592653589793}},
    "cargo_box": {
        "id": 7,
        "color": "green",
        "type": "small",
        "global_pose": {"x": 0, "y": 0, "z": 0,
                        "roll": 0, "pitch": 0, "yaw": 0}
    }
}
# ------------------------------------------------------------------


print(f"Publishing order {correlation_id} to {BROKER}:{PORT} topic '{TOPIC}'")

client = mqtt.Client()
client.connect(BROKER, PORT)
client.publish(TOPIC, json.dumps(payload))
client.disconnect()

print("✅  Static order sent.")

