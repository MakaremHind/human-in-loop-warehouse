#tools.py

from typing import Dict, Any
import logging, json, time, uuid, threading
import paho.mqtt.client as mqtt
from langchain_core.tools import tool
from models import Envelope, normalize_message
from mqtt_listener import get
from snapshot_manager import snapshot_store   # keeps type checkers happy


# MQTT CONFIG
BROKER  = "192.168.50.100"
PORT    = 1883
ORDER_REQUEST_TOPIC        = "base_01/order_request"
ORDER_RESPONSE_BASE_TOPIC  = "base_01/order_request/response"

# SHARED STATE
_order_results: Dict[str, Dict[str, Any]] = {}
_result_listener_started = False
cancelled_orders = set()
current_order_id  = None

# INTERNAL UTILITIES
def _nf(entity: str, key: Any) -> Dict[str, Any]:
    """Return a standard ‘not-found’ payload."""
    return {"found": False, "error": f"{entity} '{key}' not found"}

def _iter_modules():
    env = get("base_01/base_module_visualization")
    if not env:
        return []
    # accept either normalised form (“items”) or raw form (“modules”)
    return (
        env.data.get("items")                 # preferred, after normalisation
        or env.data.get("modules", [])        # raw, just in case
    )



def _pose_from_module(namespace: str):
    modules = _iter_modules()
    print(f"[DEBUG] Looking for module '{namespace}' in {[m['namespace'] for m in modules]}")
    if not modules:
        raise ValueError("No modules available in base_01/base_module_visualization snapshot")

    for m in modules:
        if m["namespace"] == namespace:
            return m["pose"]

    raise ValueError(f"Module '{namespace}' not found")


def _start_result_listener():
    def on_message(client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        cid = payload.get("header", {}).get("correlation_id")

        if cid in cancelled_orders and not payload.get("_republished", False):
            print(f"[listener] ⚠ Ignoring response for canceled order {cid}")
            return

        _order_results[cid] = payload

        # 🔍 Check success status
        status = "SUCCESS" if payload.get("success", False) else "FAILED"
        print(f"[listener] Got result for order {cid} — {status}")

    client = mqtt.Client()
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.subscribe(f"{ORDER_RESPONSE_BASE_TOPIC}/#")
    threading.Thread(target=client.loop_forever, daemon=True).start()


# TOOL DEFINITIONS
@tool
def list_boxes() -> list:
    """Return `[id, color, kind]` for every visible box (without pose)."""
    env = get("inventory/boxes")
    if not env:
        return []
    return [{"id": b["id"], "color": b["color"], "kind": b["kind"]}
            for b in env.data["items"]]

@tool(args_schema={"box_id": int})
def find_box(box_id: int):
    """Find a box by numeric id and return its pose and attributes."""
    env = get("inventory/boxes")
    if not env:
        return _nf("box", box_id)
    for b in env.data["items"]:
        if b["id"] == box_id:
            return {"found": True, **b}
    return _nf("box", box_id)

@tool(args_schema={"color": str})
def find_box_by_color(color: str):
    """
    Return the first box whose `color` field matches the given value.
    If no such box exists, `found` will be False.
    """
    env = get("inventory/boxes")
    if not env:
        return _nf("box(color)", color)
    for b in env.data["items"]:
        if b["color"] == color:
            return {"found": True, **b}
    return _nf("box(color)", color)

@tool(args_schema={"namespace": str})
def find_module(namespace: str):
    """Find a module by namespace and return its pose and attributes."""
    env = get("base_01/base_module_visualization")
    if not env:
        return _nf("modules", namespace)

    # Try both key options
    modules_list = []
    if "items" in env.data:
        modules_list = env.data["items"]
    elif "modules" in env.data:
        modules_list = env.data["modules"]

    print("[DEBUG] Found modules:", [m["namespace"] for m in modules_list])

    for m in modules_list:
        if m["namespace"] == namespace:
            return {"found": True, **m}

    return _nf("module", namespace)



@tool
def find_last_order(args: dict = {}) -> dict:
    """Returns the most recently completed order from the warehouse."""
    topic = "base_01/order_request"
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
    "goal":  str,
    "color": str,
    "box_id": int
})
def trigger_order(start: str, goal: str, color: str, box_id: int) -> dict:
    """
    Build and publish a transport order.

    • Looks up live poses of `start` and `goal` modules.  
    • Publishes to `base_01/order_request`.  
    • Starts a background listener (once) for order results.  
    • Returns an ACK with `correlation_id`.
    """
    global _result_listener_started, current_order_id

    # Start listener once
    if not _result_listener_started:
        _start_result_listener()
        _result_listener_started = True

    # Pose look-ups
    try:
        start_pose = _pose_from_module(start)
        goal_pose  = _pose_from_module(goal)
    except ValueError as exc:
        return {"found": False, "error": str(exc)}

    correlation_id  = str(uuid.uuid4())
    current_order_id = correlation_id

    payload = {
        "header": {
            "timestamp": time.time(),
            "sender_id": "OrderGenerator",
            "correlation_id": correlation_id
        },
        "starting_module": {
            "namespace": start,
            "pose": start_pose
        },
        "goal": {
            "namespace": goal,
            "pose": goal_pose
        },
        "cargo_box": {
            "id": box_id,
            "color": color,
            "type": "small",
            "global_pose": {
                "x": 0, "y": 0, "z": 0,
                "roll": 0, "pitch": 0, "yaw": 0
            }
        }
    }

    # MQTT publish
    client = mqtt.Client()
    client.connect(BROKER, PORT)
    client.publish(ORDER_REQUEST_TOPIC, json.dumps(payload))
    print(f"[trigger_order] ➡ Dispatched order {correlation_id}")

    return {"found": True,
            "message": "Order dispatched. Await result asynchronously.",
            "correlation_id": correlation_id}

@tool(args_schema={"correlation_id": str})
def cancel_order(correlation_id: str):
    """
    Ignore the incoming result for a given correlation-id (soft cancel),
    and proactively send a failure response to the broker.
    """
    global current_order_id

    if correlation_id in _order_results:
        return {
            "found": False,
            "error": "Order already finished; cannot cancel."
        }

    # Track as canceled
    cancelled_orders.add(correlation_id)
    if current_order_id == correlation_id:
        current_order_id = None

    # Build response payload
    response = {
        "header": {
            "timestamp": time.time(),
            "module_id": "0",
            "correlation_id": correlation_id,
            "version": 1.0,
            "duplicate": False
        },
        "success": False
    }

    # Publish to the correct MQTT topic
    topic = f"base_01/order_request/response/{correlation_id}"
    client = mqtt.Client()
    client.connect(BROKER, PORT)
    client.publish(topic, json.dumps(response))
    client.disconnect()

    return {
        "found": True,
        "message": "Order canceled; future result ignored and failure response sent."
    }
    
@tool
def confirm_last_order():
    """Report whether the most recently received order succeeded or failed."""
    if not _order_results:
        return {"found": False, "error": "No recent order result available."}

    cid = sorted(_order_results.keys())[-1]
    latest_order_result = _order_results[cid]
    success = latest_order_result.get("success", False)
    if success:
        msg = f"Order `{cid}` was completed successfully."
    else:
        msg = f"Order `{cid}` failed or was canceled."

    return {"found": True, "message": msg}


# PUBLIC EXPORT
ALL_TOOLS = [
    find_box,
    find_box_by_color,
    find_module,
    list_boxes,
    find_last_order,
    trigger_order,
    cancel_order,
    confirm_last_order
]

# Default log level
logging.getLogger().setLevel(logging.INFO)
