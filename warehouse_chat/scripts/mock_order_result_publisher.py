import paho.mqtt.client as mqtt
import json
import time
from uuid import uuid4

# --- Config ---
BROKER = "localhost"
PORT = 1883
TOPIC = "base_01/order_request/response"

# --- Simulated result message ---
correlation_id = str(uuid4())  # If you're simulating a real one, you can paste the real ID here
payload = {
    "header": {
        "timestamp": time.time(),
        "sender_id": "ManualResultPublisher",
        "correlation_id": correlation_id
    },
    "success": True
}

# --- Publish ---
client = mqtt.Client()
client.connect(BROKER, PORT, 60)
client.loop_start()

client.publish(TOPIC, json.dumps(payload), qos=1)
print(f"Published order result to '{TOPIC}' with correlation_id = {correlation_id}")

client.loop_stop()
client.disconnect()
