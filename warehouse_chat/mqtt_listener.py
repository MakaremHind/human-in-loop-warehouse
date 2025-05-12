# mqtt_listener.py
import json, threading, logging, paho.mqtt.client as mqtt
from typing import Dict, Optional
from models import normalize_message, Envelope

BROKER = "localhost"
TOPICS = [
    "/inventory/boxes",
    "/vision/fiducials",
    "/system/modules",
    "/layout/regions",
]

latest: Dict[str, Envelope] = {}   # ← one‑stop live cache

# basic logger
logging.basicConfig(level=logging.WARNING,    # was INFO
                    format="[%(asctime)s] %(levelname)s - %(message)s",
                    datefmt="%H:%M:%S")



def _on_msg(_cli, _userdata, msg):
    try:
        raw = json.loads(msg.payload)
        env = normalize_message(raw)
        latest[msg.topic] = env

        
        hdr   = raw["header"]
        ident = f"{hdr.get('module_id')}/{hdr.get('correlation_id')[:6]}"
        logging.info(
            "MQTT %-18s → %-10s  %-17s  (%d items)",
            msg.topic,
            ident,
            env.type,
            len(env.data["items"]),
        )

        # snapshot for offline debugging
        with open("snapshot.json", "w") as f:
            json.dump({k: e.model_dump() for k, e in latest.items()}, f, indent=2)

    except Exception as e:
        logging.warning("MQTT parse error on %s: %s", msg.topic, e)

def _listener():
    cli = mqtt.Client()
    cli.on_message = _on_msg
    cli.connect(BROKER, 1883, 60)
    for t in TOPICS:
        cli.subscribe(t)
    logging.info("[MQTT] listening on 9 %s", BROKER)
    cli.loop_forever()

#  background thread
threading.Thread(target=_listener, daemon=True).start()

# helper for tools
def get(topic: str) -> Optional[Envelope]:
    return latest.get(topic)
