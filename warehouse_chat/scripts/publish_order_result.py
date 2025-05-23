import paho.mqtt.client as mqtt
import time
import json
from uuid import uuid4

client = mqtt.Client()
client.connect("localhost", 1883, 60)

order_result = {
    "header": {
        "timestamp": time.time(),
        "sender_id": "mock_result_sender",
        "correlation_id": str(uuid4())
    },
    "starting_module": {
        "namespace": "conveyor_02",
        "pose": {"x": 100, "y": 200, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
    },
    "goal": {
        "namespace": "container_01",
        "pose": {"x": 300, "y": 400, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
    },
    "cargo_box": {
        "id": 999,
        "color": "blue",
        "type": "small",
        "global_pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
    }
}

client.publish("base_01/order_request/response", json.dumps(order_result), qos=1)
print("[✔] Published order result.")
client.disconnect()
