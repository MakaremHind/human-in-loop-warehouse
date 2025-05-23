import paho.mqtt.client as mqtt
import json

BROKER = "192.168.50.100"
PORT = 1883
TOPIC = "base_01/order_request/response"

def on_connect(client, userdata, flags, rc):
    print(f"[Listener] Connected with result code {rc}")
    client.subscribe(TOPIC)
    print(f"[Listener] Subscribed to '{TOPIC}'")

def on_message(client, userdata, msg):
    print(f"\n[Listener]  Message received on topic: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        print(f"[Listener] Parsed result:\n{json.dumps(payload, indent=2)}")
    except Exception as e:
        print(f"[Listener] Failed to parse payload: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"[Listener] Connecting to MQTT broker at {BROKER}:{PORT}...")
client.connect(BROKER, PORT, 60)
client.loop_forever()
