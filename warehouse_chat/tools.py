#tools.py

from typing import Dict, Any
import logging, json, time, uuid, threading
import paho.mqtt.client as mqtt
from langchain_core.tools import tool
from models import Envelope, normalize_message
from mqtt_listener import get
from snapshot_manager import snapshot_store   # keeps type checkers happy
from typing import List
from mqtt_listener import BROKER_CONNECTED, LAST_MASTER_MSG
ONLINE_TIMEOUT = 30.0      # seconds without a master message → “offline”



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


@tool
def master_status() -> dict:
    """
    Return {'online': bool, 'since': <seconds>} telling whether the Master
    controller appears alive (based on recent MQTT traffic under 'master/…').
    """
    if not BROKER_CONNECTED:
        return {"online": False, "since": None,
                "info": "MQTT broker unreachable"}

    age = time.time() - LAST_MASTER_MSG
    return {
        "online": age < ONLINE_TIMEOUT,
        "since" : round(age, 1)          # age of last heartbeat
    }
    
    
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
    """Return `[id, color, type]` for every detected box (no pose)."""
    env = get("mmh_cam/detected_boxes")
    if not env:
        return []
    return [{"id": i, "color": b["color"], "type": b["type"]}
            for i, b in enumerate(env.data["boxes"])]

@tool(args_schema={"box_id": int})
def find_box(box_id: int):
    """Find a box by index in the list and return full box data including pose."""
    env = get("mmh_cam/detected_boxes")
    if not env or not env.data["boxes"]:
        return _nf("box", box_id)
    if 0 <= box_id < len(env.data["boxes"]):
        return {"found": True, **env.data["boxes"][box_id]}
    return _nf("box", box_id)

@tool(args_schema={"color": str})
def find_box_by_color(color: str):
    """
    Return the first box with matching color.
    If none found, returns `found: False`.
    """
    env = get("mmh_cam/detected_boxes")
    if not env or not env.data["boxes"]:
        return _nf("box(color)", color)
    for b in env.data["boxes"]:
        if b["color"].lower() == color.lower():
            return {"found": True, **b}
    return _nf("box(color)", color)

@tool
def list_modules() -> List[str]:
    """Returns the list of all available module namespaces (e.g., conveyors, containers, docks, etc.)"""
    snapshot = get("base_01/base_module_visualization")
    if not snapshot:
        return []

    # Accept normalized or raw format
    modules = (
        snapshot.data.get("items")
        or snapshot.data.get("modules", [])
    )
    return [m["namespace"] for m in modules if "namespace" in m]

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


# === Updated diagnose_failure tool ===
from langchain_core.tools import tool
from mqtt_listener import get
from snapshot_manager import snapshot_store

@tool
def diagnose_failure() -> dict:
    """
    Diagnose the reason for a failed order by scanning relevant MQTT log topics,
    regardless of correlation ID.

    It checks:
    - `base_01/*/transport/response` for success=false
    - `master/logs/execute_planned_path` for module execution failures
    - `master/logs/search_for_box_in_starting_module_workspace` for missing boxes
    """

    reasons = []

    for topic, payload in snapshot_store.snapshots.items():
        if not isinstance(payload, dict):
            continue

        msg = json.dumps(payload)

        # --- Topic-specific failure indicators ------------------------

        if "base_01/" in topic and topic.endswith("/transport/response"):
            if not payload.get("success", True):
                reasons.append(f"Transport failure reported in {topic}.")

        elif topic == "master/logs/execute_planned_path":
            message = payload.get("message", "")
            if "Transport failed" in message:
                reasons.append("Transport failed at a module during execution.")

        elif topic == "master/logs/search_for_box_in_starting_module_workspace":
            message = payload.get("message", "")
            if "No box found" in message:
                reasons.append("No box found in starting module workspace.")

    # collapse duplicates
    seen = set()
    unique_reasons = [r for r in reasons if not (r in seen or seen.add(r))]

    if not unique_reasons:
        return {
            "found": False,
            "error": "No known failure messages found in relevant topics."
        }

    return {
        "found": True,
        "reason": "; ".join(unique_reasons)
    }


# PUBLIC EXPORT
ALL_TOOLS = [
    find_box,
    find_box_by_color,
    find_module,
    list_boxes,
    find_last_order,
    trigger_order,
    cancel_order,
    confirm_last_order,
    diagnose_failure,
    list_modules,
    master_status
]

# Default log level
logging.getLogger().setLevel(logging.INFO)

# ────────── SINGLE-STRING WRAPPERS for MRKL agent ──────────
from typing import Any, Dict
from langchain.agents import Tool

def _parse_kv(arg: str) -> Dict[str, str]:
    result = {}
    for part in arg.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
        elif "=" in part:
            k, v = part.split("=", 1)
        else:
            continue
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result

# ---- helpers that accept *either* string or dict -----------
def _ensure_dict(inp: Any) -> Dict[str, Any]:
    if isinstance(inp, dict):
        return inp
    if isinstance(inp, str):
        inp = inp.strip()
        try:
            return json.loads(inp)
        except json.JSONDecodeError:
            if "=" in inp or ":" in inp:
                return _parse_kv(inp)
            else:
                return {"namespace": inp}
    raise ValueError("Unsupported input type")



# ---------- one wrapper per original tool -------------------
def find_box_wrap(arg: Any):
    d = _ensure_dict(arg)
    if "box_id" not in d:
        raise ValueError("find_box expects box_id:int, but none was provided.")
    d["box_id"] = int(d["box_id"])  # ensure int
    return find_box.invoke(d)


def find_box_by_color_wrap(arg: Any):
    d = _ensure_dict(arg)
    if "color" not in d and arg:
        d = {"color": str(arg).strip()}
    return find_box_by_color.invoke(d)

def find_module_wrap(arg: Any):
    d = _ensure_dict(arg)
    if "namespace" not in d and arg:
        d = {"namespace": str(arg).strip()}
    return find_module.invoke(d)

def trigger_order_wrap(arg: Any):
    d = _ensure_dict(arg)
    required = {"start", "goal", "color", "box_id"}
    if not required.issubset(d):
        raise ValueError(f"trigger_order expects {required}")
    d["box_id"] = int(d["box_id"])
    print("[DEBUG] Parsed trigger_order args:", d)
    return trigger_order.invoke(d)

def cancel_order_wrap(arg: Any):
    d = _ensure_dict(arg)
    cid = d.get("correlation_id", str(arg).strip())
    return cancel_order.invoke({"correlation_id": cid})

def diagnose_failure_wrap(_: Any = ""):
    return diagnose_failure.invoke({})


# tools without args
list_boxes_wrap        = lambda _="": list_boxes.invoke({})
find_last_order_wrap   = lambda _="": find_last_order.invoke({})
confirm_last_order_wrap= lambda _="": confirm_last_order.invoke({})

# ---------- MRKL-compatible toolkit -------------------------
MRKL_TOOLS = [
    Tool("find_box",           find_box_wrap,
         "find_box(box_id:int)  → pose & attributes"),
    Tool("find_box_by_color",  find_box_by_color_wrap,
         "find_box_by_color(color:str)"),
    Tool("find_module",        find_module_wrap,
         "find_module(namespace:str)"),
    Tool("list_boxes",         list_boxes_wrap,
         "list_boxes() → summary of boxes"),
    Tool("find_last_order",    find_last_order_wrap,
         "find_last_order() → last completed order"),
    Tool("trigger_order",      trigger_order_wrap,
         ("trigger_order(start:str, goal:str, color:str, "
          "box_id:int) → dispatch order")),
    Tool("cancel_order",       cancel_order_wrap,
         "cancel_order(correlation_id:str)"),
    Tool("confirm_last_order", confirm_last_order_wrap,
         "confirm_last_order() → success / failed"),
    Tool("diagnose_failure", diagnose_failure_wrap,
     "diagnose_failure() → reason for last known failure"),
    Tool("list_modules", lambda _="": list_modules.invoke({}),
         "list_modules() → all available module namespaces"),
    Tool("master_status", lambda _="": master_status.invoke({}),
         "master_status() → is the master online?")
]

