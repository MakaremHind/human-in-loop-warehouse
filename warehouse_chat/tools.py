from typing import Dict, Any
import logging, json, time, uuid, threading
from langchain_core.tools import tool
import paho.mqtt.client as mqtt
from models import Envelope, normalize_message
from mqtt_listener import get
from snapshot_manager import snapshot_store

BROKER = "localhost"
ORDER_REQUEST_TOPIC = "base_01/order_request"
ORDER_RESULT_TOPIC = "base_01/order_result"

_order_results = {}
_order_lock = threading.Lock()
_result_listener_started = False

def _start_result_listener():
    def on_message(client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        cid = payload.get("header", {}).get("correlation_id")
        if cid:
            with _order_lock:
                _order_results[cid] = payload

    client = mqtt.Client()
    client.connect(BROKER, 1883, 60)
    client.subscribe(ORDER_RESULT_TOPIC)
    client.on_message = on_message
    thread = threading.Thread(target=client.loop_forever, daemon=True)
    thread.start()

def _nf(entity: str, key: Any) -> Dict[str, Any]:
    return {"found": False, "error": f"{entity} '{key}' not found"}

logging.getLogger().setLevel(logging.INFO)

@tool
def list_boxes() -> list:
    """Return summary (ID, color, kind) of all visible boxes. No pose info included."""
    env = get("inventory/boxes")
    if not env:
        print("DEBUG: No snapshot available for inventory/boxes")
        return []
    print("DEBUG: Snapshot contains:", env.data["items"])
    return [{"id": b["id"], "color": b["color"], "kind": b["kind"]} for b in env.data["items"]]

@tool(args_schema={"box_id": int})
def find_box(box_id: int):
    """Return pose of the box with given id."""
    env = get("inventory/boxes")
    logging.info("find_box(%s)  → snapshot %s", box_id, "HIT" if env else "MISS")

    if not env:
        return _nf("box", box_id)
    for b in env.data["items"]:
        if b["id"] == box_id:
            return {"found": True, **b}
    return _nf("box", box_id)

@tool(args_schema={"namespace": str})
def find_module(namespace: str):
    """Return pose of a module by namespace."""
    env = get("system/modules")
    logging.info("find_module(%s) → snapshot %s", namespace, "HIT" if env else "MISS")

    if not env:
        return _nf("module", namespace)
    for m in env.data["items"]:
        if m["namespace"] == namespace:
            return {"found": True, **m}
    return _nf("module", namespace)

@tool(args_schema={"color": str})
def find_box_by_color(color: str):
    """Return the first box matching the given color."""
    env = get("inventory/boxes")
    logging.info("find_box_by_color(%s) → snapshot %s", color, "HIT" if env else "MISS")

    if not env:
        return _nf("box", color)

    matches = [b for b in env.data["items"] if b["color"].lower() == color.lower()]
    if not matches:
        return _nf("box", color)

    return {"found": True, **matches[0]}

@tool(args_schema={
    "start": str,
    "goal": str,
    "color": str,
    "box_id": int
})
def trigger_order(start: str, goal: str, color: str, box_id: int):
    """Trigger a transport order and wait for result in background."""

    global _result_listener_started
    if not _result_listener_started:
        _start_result_listener()
        _result_listener_started = True

    correlation_id = str(uuid.uuid4())
    payload = {
        "header": {
            "timestamp": time.time(),
            "sender_id": "chatbot",
            "correlation_id": correlation_id
        },
        "starting_module": {
            "namespace": start,
            "pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
        },
        "goal": {
            "namespace": goal,
            "pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
        },
        "cargo_box": {
            "id": box_id,
            "color": color,
            "type": "small",
            "global_pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
        }
    }

    client = mqtt.Client()
    client.connect(BROKER, 1883, 60)
    client.publish(ORDER_REQUEST_TOPIC, json.dumps(payload))
    client.disconnect()

    # Wait for result
    for _ in range(20):  # wait up to 10 seconds
        time.sleep(0.5)
        with _order_lock:
            if correlation_id in _order_results:
                result = _order_results.pop(correlation_id)
                return {
                    "found": True,
                    "success": result.get("success", False),
                    "details": result
                }

    return {
        "found": False,
        "error": f"Order timed out waiting for result (correlation_id={correlation_id})"
    }

@tool
def find_last_order(args: dict = {}) -> dict:
    """Returns the most recently completed order from the warehouse."""
    topic = "base_01/order_result"
    data = snapshot_store.get(topic)
    if not data:
        return {"found": False, "error": "No recent order found."}

    try:
        env = normalize_message(data)
        return {"found": True, "order": env.data["order"]}
    except Exception as e:
        return {"found": False, "error": f"Failed to normalize order: {e}"}

ALL_TOOLS = [
    find_box,
    find_box_by_color,
    find_module,
    list_boxes,
    find_last_order,
    trigger_order
]
