#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# mqtt_listener.py – captures all live MQTT traffic we care about
# -----------------------------------------------------------------------------
# This module subscribes to relevant MQTT topics, stores raw and normalized
# snapshots, and provides helper accessors for other modules. All logic is
# preserved as in the original code.
# -----------------------------------------------------------------------------

import json, logging, time
import paho.mqtt.client as mqtt
from models import normalize_message
from snapshot_manager import snapshot_store

logging.basicConfig(level=logging.ERROR)

BROKER = "192.168.50.100"
PORT   = 1883

BROKER_CONNECTED = False          # becomes True after successful connect
LAST_MASTER_MSG  = 0.0            # unix-time of last message on any “master/…” topic

# -----------------------------------------------------------------------------
# TOPICS TO SUBSCRIBE
# -----------------------------------------------------------------------------
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
    "master/logs/search_for_box_in_starting_module_workspace/warning",
    "master/state", 
]

# local in-memory cache for Envelope-type snapshots
snapshots: dict[str, object] = {}

# -----------------------------------------------------------------------------
# MQTT CALLBACKS
# -----------------------------------------------------------------------------
def on_connect(client, userdata, flags, rc, properties=None):
    global BROKER_CONNECTED
    if rc == 0:
        BROKER_CONNECTED = True
        logging.info("Connected to MQTT broker.")
        for t in TOPICS:
            client.subscribe(t)
    else:
        logging.warning("Failed to connect to MQTT broker (rc=%s)", rc)


def on_message(client, userdata, msg):
    global LAST_MASTER_MSG
    topic = msg.topic.lstrip("/")         # normalise
    try:
        payload = json.loads(msg.payload.decode())
        snapshot_store.store(topic, payload)      # save raw JSON
        # update helper timestamp if this is any master/… topic
        if topic.startswith("master/"):
            LAST_MASTER_MSG = time.time()
        # keep “system/modules” convenience snapshot
        if topic.endswith("base_module_visualization"):
            modules = payload.get("modules", [])
            snapshot_store.store("system/modules", {"items": modules})
        # try normalising
        try:
            env = normalize_message(payload)
            snapshots[topic] = env
            if topic.startswith("base_01/order_request/response"):
                print(f"[DEBUG] Received order response on topic '{topic}'")
        except ValueError as ve:
            logging.debug("Ignored message on %s: %s", topic, ve)
    except Exception as e:
        logging.warning("Failed to parse MQTT %s: %s", msg.topic, e)

# -----------------------------------------------------------------------------
# MQTT CLIENT INIT
# -----------------------------------------------------------------------------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
try:
    client.connect(BROKER, PORT, keepalive=30)
    BROKER_CONNECTED = True
except Exception as e:
    logging.error("Could not connect to MQTT broker: %s", e)

client.loop_start()                        # background thread

# -----------------------------------------------------------------------------
# HELPER ACCESSOR
# -----------------------------------------------------------------------------
def get(topic: str):
    """Return last normalised snapshot for *exact* topic."""
    env = snapshots.get(topic)
    if env is None:
        print(f"[DEBUG] Snapshot not found for topic: {topic}")
    else:
        print(f"[DEBUG] Snapshot found for topic: {topic}")
    return env

# -----------------------------------------------------------------------------
# HEALTH-CHECK HELPERS
# -----------------------------------------------------------------------------
def is_broker_online() -> bool:
    """True if we managed to connect to MQTT broker."""
    return BROKER_CONNECTED


def is_master_online(timeout: float = 5.0) -> bool:
    """
    Return *True* if at least one ‘master/…’ message was seen within *timeout*
    seconds.
    """
    if LAST_MASTER_MSG == 0:
        return False                      # never heard from master
    return (time.time() - LAST_MASTER_MSG) < timeout

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------
