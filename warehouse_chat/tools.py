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
from rapidfuzz import process


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
    Check if the Master controller is online based on the latest 'master/state' message.
    """
    from mqtt_listener import snapshot_store

    # use raw payload (not normalized)
    payload = snapshot_store.snapshots.get("master/state")
    if not payload:
        return {
            "online": False,
            "info": "No message received from master/state"
        }

    status = str(payload.get("data", "")).lower()
    is_online = status == "online"

    return {
        "online": is_online,
        "info": f"Master state: {status}"
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

# ── list every cached order result ───────────────────────────────────────
# ── list every order response currently cached ────────────────────────────
@tool
def list_orders() -> dict:
    """
    Return **all** order-response payloads held in `snapshot_store`
    (newest first).
    """
    from snapshot_manager import snapshot_store

    orders = [
        p for t, p in snapshot_store.snapshots.items()
        if t.startswith("base_01/order_request/response")
    ]
    if not orders:
        return {"found": False,
                "error": "No order responses present in snapshot_store."}

    orders.sort(key=lambda p: p.get("header", {}).get("timestamp", 0),
                reverse=True)
    return {"found": True, "orders": orders}



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
# ── unified trigger_order tool ────────────────────────────────────────────
@tool(args_schema={
    "start":       str,
    "goal":        str,
    "start_pose":  dict,
    "goal_pose":   dict,

    # optional cargo-box overrides
    "box_id":      int,
    "box_color":   str,
    "box_pose":    dict,

    # optional – how long (s) to wait for a response
    "wait_timeout": int
})
def trigger_order(*,
                  start: str | None = None,
                  goal: str | None = None,
                  start_pose: dict | None = None,
                  goal_pose:  dict | None = None,
                  box_id:     int  | None = None,
                  box_color:  str  | None = None,
                  box_pose:   dict | None = None,
                  wait_timeout: int = 60) -> dict:
    """
    Dispatch a transport order **and block until the master answers** or
    *wait_timeout* seconds elapse.

    Required (pick one in each row):
    • `start`      **or** `start_pose`
    • `goal`       **or** `goal_pose`

    Optional cargo-box overrides: `box_id`, `box_color`, `box_pose`.
    """

    # ── 0. make sure the background listener runs ────────────────────
    global _result_listener_started, current_order_id
    if not _result_listener_started:
        _start_result_listener()
        _result_listener_started = True

    # ── 1. resolve start / goal poses ─────────────────────────────────
    try:
        if start is not None:
            start_pose_val, start_ns = _pose_from_module(start), start
        elif start_pose is not None:
            start_pose_val, start_ns = start_pose, "manual_pose_start"
        else:
            raise ValueError("provide either 'start' or 'start_pose'")

        if goal is not None:
            goal_pose_val,  goal_ns  = _pose_from_module(goal), goal
        elif goal_pose is not None:
            goal_pose_val,  goal_ns  = goal_pose, "manual_pose_goal"
        else:
            raise ValueError("provide either 'goal' or 'goal_pose'")

    except ValueError as exc:
        return {"found": False, "error": str(exc)}

    # ── 2. build & publish MQTT payload ───────────────────────────────
    correlation_id   = str(uuid.uuid4())
    current_order_id = correlation_id

    cargo_box = {
        "id":    box_id    if box_id    is not None else 7,
        "color": box_color if box_color is not None else "red",
        "type":  "small",
        "global_pose": box_pose if box_pose is not None else
                       {"x": 0, "y": 0, "z": 0,
                        "roll": 0, "pitch": 0, "yaw": 0}
    }

    payload = {
        "header": {
            "timestamp": time.time(),
            "sender_id": "OrderGenerator",
            "correlation_id": correlation_id
        },
        "starting_module": {"namespace": start_ns, "pose": start_pose_val},
        "goal":            {"namespace": goal_ns,   "pose": goal_pose_val},
        "cargo_box":       cargo_box
    }

    client = mqtt.Client()
    client.connect(BROKER, PORT)
    client.publish(ORDER_REQUEST_TOPIC, json.dumps(payload))
    client.disconnect()

    print(f"[trigger_order] ➡ Dispatched order {correlation_id}")

    # ── 3. wait for the matching response ─────────────────────────────
    t0 = time.time()
    while time.time() - t0 < wait_timeout:
        result = _order_results.get(correlation_id)
        if result:                       # got it!
            success = bool(result.get("success", False))
            return {
                "found": True,
                "correlation_id": correlation_id,
                "success": success,
                "response": result
            }
        time.sleep(0.5)

    # timed out
    return {
        "found": False,
        "correlation_id": correlation_id,
        "error": f"No response within {wait_timeout}s."
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
    confirm_last_order,
    diagnose_failure,
    list_modules,
    master_status,
    list_orders
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
    try:
        if isinstance(arg, int):
            d = {"box_id": arg}
        elif isinstance(arg, dict):
            d = arg
        elif isinstance(arg, str):
            arg = arg.strip()
            if arg.isdigit():
                d = {"box_id": int(arg)}
            else:
                d = _ensure_dict(arg)
        else:
            d = _ensure_dict(arg)

        if "box_id" not in d:
            raise ValueError("find_box expects box_id:int, but none was provided.")

        d["box_id"] = int(d["box_id"])  # ensure type safety
        return find_box.invoke(d)
    except Exception as e:
        return {"found": False, "error": f"Invalid input to find_box: {e}"}




def find_box_by_color_wrap(arg: Any):
    d = _ensure_dict(arg)
    if "color" not in d and arg:
        d = {"color": str(arg).strip()}
    return find_box_by_color.invoke(d)

def find_module_wrap(arg: Any):
    d = _ensure_dict(arg)
    if "namespace" not in d and arg:
        d = {"namespace": str(arg).strip()}

    original = d["namespace"]

    # Get all available module names
    known_modules = list_modules.invoke({})

    # Fuzzy match
    best_match, score, _ = process.extractOne(original, known_modules)

    if score > 80:  # threshold can be adjusted
        print(f"[FuzzyMatch] Interpreting '{original}' as '{best_match}' (score: {score})")
        d["namespace"] = best_match
    else:
        print(f"[FuzzyMatch] No close match found for '{original}' (best was '{best_match}', score: {score})")

    return find_module.invoke(d)

# ── MRKL wrapper for trigger_order ────────────────────────────────────────
# ──────────────── trigger_order_wrap (handles *all* cases) ────────────────
import ast, json, re

def trigger_order_wrap(arg: Any) -> dict:
    """
    Wrapper around trigger_order that handles string, dict, and mixed inputs.
    Supports fuzzy module matching and auto-fills box pose if only box ID or color is given.
    """

    def parse_input(arg: Any) -> dict:
        if isinstance(arg, dict):
            return arg
        if isinstance(arg, str):
            try:
                return json.loads(arg)
            except json.JSONDecodeError:
                return _parse_kv(arg)
        raise ValueError("Unsupported input format")

    try:
        args = parse_input(arg)

        # Normalize start/goal module names (fuzzy match via find_module_wrap)
        if "start" in args:
            start_info = find_module_wrap(args["start"])
            if not start_info.get("found"):
                return {"found": False, "error": f"Invalid start module '{args['start']}'"}
            args["start_pose"] = start_info["pose"]
            args["start"] = start_info["namespace"]

        if "goal" in args:
            goal_info = find_module_wrap(args["goal"])
            if not goal_info.get("found"):
                return {"found": False, "error": f"Invalid goal module '{args['goal']}'"}
            args["goal_pose"] = goal_info["pose"]
            args["goal"] = goal_info["namespace"]

        # Normalize box data
        if "box_id" in args:
            try:
                box_info = find_box_wrap({"box_id": int(args["box_id"])})
            except Exception:
                box_info = {"found": False}
        elif "box_color" in args:
            box_info = find_box_by_color_wrap({"color": args["box_color"]})
        else:
            box_info = {"found": False}

        if box_info.get("found", False):
            args.setdefault("box_id", box_info.get("id"))
            args.setdefault("box_color", box_info.get("color"))
            args.setdefault("box_pose", box_info.get("global_pose"))

        # Clean up input for trigger_order
        final_args = {
            "start": args.get("start"),
            "goal": args.get("goal"),
            "start_pose": args.get("start_pose"),
            "goal_pose": args.get("goal_pose"),
            "box_id": args.get("box_id"),
            "box_color": args.get("box_color"),
            "box_pose": args.get("box_pose"),
            "wait_timeout": int(args.get("wait_timeout", 60))
        }

        return trigger_order.invoke(final_args)

    except Exception as e:
        return {"found": False, "error": f"trigger_order_wrap failed: {e}"}


# tools without args
list_boxes_wrap        = lambda _="": list_boxes.invoke({})
find_last_order_wrap   = lambda _="": find_last_order.invoke({})
confirm_last_order_wrap= lambda _="": confirm_last_order.invoke({})
diagnose_failure_wrap   = lambda _="": diagnose_failure.invoke({})
list_orders_wrap        = lambda _="": list_orders.invoke({})

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
    Tool("trigger_order", trigger_order_wrap,
    (
        "trigger_order(start|start_pose, goal|goal_pose "
        "[, box_id:int, box_color:str, box_pose:dict, wait_timeout:int]) "
        "→ dispatch the order **and wait for the master’s response**.\n"
        "Examples:\n"
        "  • trigger_order(start=container_02, goal=container_01, box_color=blue)\n"
        "  • trigger_order(x=0.4, y=0.3, goal=dock_03,\n"
        "                 bx=0.9, by=0.1, box_id=42, wait_timeout=120)"
    )),
    Tool("confirm_last_order", confirm_last_order_wrap,
         "confirm_last_order() → success / failed"),
    Tool("diagnose_failure", diagnose_failure_wrap,
     "diagnose_failure() → reason for last known failure"),
    Tool("list_modules", lambda _="": list_modules.invoke({}),
         "list_modules() → all available module namespaces"),
    Tool("master_status", lambda _="": master_status.invoke({}),
         "master_status() → is the master online?"),
    Tool("list_orders", list_orders_wrap,
         "list_orders() → every cached order result (newest first)")
]

