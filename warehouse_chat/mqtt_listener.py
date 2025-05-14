# mqtt_listener.py – Updated to normalize messages using Envelope

import json
import logging
import paho.mqtt.client as mqtt
from models import normalize_message, Envelope

logging.basicConfig(level=logging.ERROR)


# Global snapshot dictionary
snapshots = {}

# MQTT broker config
BROKER = "192.168.50.100"
PORT = 1883

TOPICS = [
    "/inventory/boxes", 
    "/mmh_cam/detected_markers",
    "/base_01/uarm_01",
    "/base_01/uarm_02",
    "/base_01/conveyor_02",
    "/base_module_visualization",
    "/height_map",
    "/system/modules",
    "/layout/regions"
]

def on_message(client, userdata, msg):
    try:
        logging.debug(f"[MQTT] Received topic: {msg.topic}")
        raw = json.loads(msg.payload.decode())

        # Assume message is already in Envelope format
        env = normalize_message(raw)
        snapshots[msg.topic] = env

        logging.info("Snapshot stored → %s (%d items)", msg.topic, len(env.data.get("items", [])))
        logging.debug("Stored payload: %s", env)

    except Exception as e:
        logging.warning("Failed to parse MQTT %s: %s", msg.topic, e)



# MQTT setup
client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER, PORT)
for topic in TOPICS:
    client.subscribe(topic)

client.loop_start()

# Access method used by tools
def get(topic: str):
    return snapshots.get(topic)