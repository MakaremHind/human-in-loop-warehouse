from typing import Dict, Any
import logging, json, time, uuid, threading
from langchain_core.tools import tool
import paho.mqtt.client as mqtt
from models import Envelope, normalize_message
from mqtt_listener import get
from snapshot_manager import snapshot_store

BROKER = "localhost"
PORT = 1883
ORDER_REQUEST_TOPIC = "base_01/order_request"
ORDER_RESULT_TOPIC = "base_01/order_request/response"

_order_results = {}
_order_lock = threading.Lock()
_result_listener_started = False

active_orders = {}
cancelled_orders = set()
result_messages = []

def _start_result_listener():
    def on_message(client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        cid = payload.get("header", {}).get("correlation_id")
        # Skip if we've already handled this cancellation
        if cid in cancelled_orders and not payload.get("_republished", False):
            print(f"[listener] ⚠ Ignored response for canceled order {cid}")
            payload["success"] = False
            payload["_republished"] = True
            client.publish(ORDER_RESULT_TOPIC, json.dumps(payload), qos=1)
            print("[listener] publish cancelling results to base_01/order_request/response")
            return 


    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)
    client.subscribe(ORDER_RESULT_TOPIC)
    client.on_message = on_message
    thread = threading.Thread(target=client.loop_forever, daemon=True)
    thread.start()


def _nf(entity: str, key: Any) -> Dict[str, Any]:
    return {"found": False, "error": f"{entity} '{key}' not found"}

logging.getLogger().setLevel(logging.INFO)

def _background_response_handler():
    def on_message(client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        cid = payload.get("header", {}).get("correlation_id")
        if cid and cid not in cancelled_orders:
            result_messages.append({
                "correlation_id": cid,
                "success": payload.get("success", False),
                "details": payload
            })

    client = mqtt.Client()
    client.connect(BROKER, 1883, 60)
    client.subscribe(ORDER_RESULT_TOPIC)
    client.on_message = on_message
    threading.Thread(target=client.loop_forever, daemon=True).start()

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
    
@tool(args_schema={
    "start": str,
    "goal": str,
    "color": str,
    "box_id": int
})
def trigger_order(start: str, goal: str, color: str, box_id: int) -> dict:
    """Trigger a transport order and wait for result in background."""
    global _result_listener_started, current_order_id
    if not _result_listener_started:
        _start_result_listener()
        _result_listener_started = True

    correlation_id = str(uuid.uuid4())
    current_order_id = correlation_id

    payload = {
        "header": {"timestamp": time.time(), "sender_id": "OrderGenerator", "correlation_id": correlation_id},
        "starting_module": {"namespace": start, "pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}},
        "goal": {"namespace": goal, "pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}},
        "cargo_box": {
            "id": box_id, "color": color, "type": "small",
            "global_pose": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}
        }
    }

    client = mqtt.Client()
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    client.publish(ORDER_REQUEST_TOPIC, json.dumps(payload), qos=1)
    client.disconnect()
    print(f"[trigger_order] Published order to {ORDER_REQUEST_TOPIC} → ID: {correlation_id}")

    active_orders[correlation_id] = {
        "start": start, "goal": goal, "box_id": box_id, "color": color, "timestamp": time.time()
    }

    return {"found": True, "correlation_id": correlation_id, "message": f"Order sent. Now tracking result for ID {correlation_id}."}

@tool(args_schema={"correlation_id": str})
def cancel_order(correlation_id: str) -> dict:
    """Cancel a running order so its result will be ignored."""
    if correlation_id in active_orders:
        cancelled_orders.add(correlation_id)
        active_orders.pop(correlation_id, None)
        global current_order_id
        if current_order_id == correlation_id:
            current_order_id = None
        return {"found": True, "message": "Order canceled. Awaited result will be ignored."}
    else:
        return {"found": False, "error": f"No active order found with ID {correlation_id}."}



ALL_TOOLS = [
    find_box,
    find_box_by_color,
    find_module,
    list_boxes,
    find_last_order,
    trigger_order,
    cancel_order
]