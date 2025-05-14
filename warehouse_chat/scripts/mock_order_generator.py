import json
import time
import paho.mqtt.client as mqtt

# MQTT broker settings
BROKER = "localhost"  # Change if needed
PORT = 1883
TOPIC = "base_01/order_request"

# Mock order payload
payload = {
    "header": {
        "timestamp": time.time(),
        "sender_id": "OrderGenerator"
    },
    "starting_module": {
        "namespace": "conveyor_02",
        "pose": {
            "x": 872.65, "y": 873.91, "z": 58,
            "roll": 0, "pitch": 0, "yaw": -3.14159265
        }
    },
    "goal": {
        "namespace": "container_01",
        "pose": {
            "x": 102.34, "y": 186.91, "z": 90,
            "roll": 0, "pitch": 0, "yaw": 1.57079633
        }
    },
    "cargo_box": {
        "id": 348,
        "color": "red",
        "type": "small",
        "global_pose": {
            "x": 0, "y": 0, "z": 0,
            "roll": 0, "pitch": 0, "yaw": 0
        }
    }
}

# Connect to broker and publish
client = mqtt.Client()
client.connect(BROKER, PORT)
client.loop_start()
client.publish(TOPIC, json.dumps(payload), qos=1)
print(f"✅ Published mock order to '{TOPIC}'")
client.loop_stop()
client.disconnect()
