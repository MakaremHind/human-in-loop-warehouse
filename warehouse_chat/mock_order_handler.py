import asyncio
import json
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

REQUEST_TOPIC = "base_01/order_request"
RESULT_TOPIC = "base_01/order_request/response"

def simulate_transport(order_msg):
    order = json.loads(order_msg)
    print(f"[Mock Handler] Received order: {order}")
    print("[Mock Handler] Simulating transport...")
    time.sleep(5)  # Simulate delay

    # Construct compatible response format
    response = {
        "header": {
            "timestamp": time.time(),
            "module_id": "mock_handler",
            "correlation_id": order["header"]["correlation_id"],
            "version": 1.0
        },
        "success": True
    }

    return json.dumps(response)

def on_message(client, userdata, msg):
    print(f"[Mock Handler] Message on topic: {msg.topic}")
    response = simulate_transport(msg.payload.decode())
    client.publish(RESULT_TOPIC, response, qos=1)
    print(f"[Mock Handler] Published result to {RESULT_TOPIC}")

def main():
    client = mqtt.Client()
    client.on_message = on_message

    print(f"[Mock Handler] Connecting to MQTT broker at {BROKER}:{PORT}...")
    client.connect(BROKER, PORT, 60)
    client.subscribe(REQUEST_TOPIC, qos=1)

    print(f"[Mock Handler] Subscribed to {REQUEST_TOPIC}. Waiting for orders...")
    client.loop_forever()

if __name__ == "__main__":
    main()
