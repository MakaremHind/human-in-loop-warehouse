import json
import time
import uuid
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "base_01/order_request"

def generate_order():
    return {
        "header": {
            "timestamp": time.time(),
            "sender_id": "OrderGenerator",
            "correlation_id": str(uuid.uuid4())
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

def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    print("[Order Generator] Starting loop...")
   
    order = generate_order()
    client.publish(TOPIC, json.dumps(order), qos=1)
    print("✅ Published mock order to", TOPIC)
    

if __name__ == "__main__":
    main()
