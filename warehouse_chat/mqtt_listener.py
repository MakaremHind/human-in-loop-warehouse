import json
import logging
import paho.mqtt.client as mqtt
from models import normalize_message
from snapshot_manager import snapshot_store

logging.basicConfig(level=logging.ERROR)

BROKER = "192.168.50.100"
PORT = 1883

TOPICS = [
    "mmh_cam/detected_markers",
    "mmh_cam/detected_boxes",
    "base_01/uarm_01",
    "base_01/uarm_02",
    "base_01/conveyor_02",
    "base_01/base_module_visualization",
    "height_map",
    "system/modules",
    "layout/regions",
    "base_01/order_request",
    "base_01/order_request/response/#",
    "base_01/order_request/response",
    "base_01/uarm_01/transport/response",
    "master/logs/execute_planned_path/info",
    "master/logs/execute_planned_path/debug",
    "master/logs/execute_planned_path/warning",
    "master/logs/search_for_box_in_starting_module_workspace/warning"
]

# Local in-memory cache for Envelope-type snapshots
snapshots = {}

def on_message(client, userdata, msg):
    topic = msg.topic.lstrip("/")  # Normalize to match expected keys
    
    try:
        payload = json.loads(msg.payload.decode())
        snapshot_store.store(topic, payload)  # Save raw JSON
        
        if topic.endswith("base_module_visualization"):
            modules = payload.get("modules", [])
            snapshot_store.store("system/modules", {"items": modules})


        # Normalize and store in memory
        try:
            env = normalize_message(payload)
            snapshots[topic] = env

            if topic.startswith("base_01/order_request/response"):
                print(f"[DEBUG] Received order response on topic '{topic}'")
        except ValueError as ve:
            logging.debug(f"Ignored message on {topic}: {ve}")

    except Exception as e:
        logging.warning("Failed to parse MQTT %s: %s", msg.topic, e)

# MQTT setup
client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER, PORT)

for topic in TOPICS:
    client.subscribe(topic)

client.loop_start()  # Non-blocking background listener

# Method used by tools to access parsed snapshots
def get(topic: str):
    env = snapshots.get(topic)
    if env is None:
        print(f"[DEBUG] Snapshot not found for topic: {topic}")
    else:
        print(f"[DEBUG] Snapshot found for topic: {topic}")
    return env


