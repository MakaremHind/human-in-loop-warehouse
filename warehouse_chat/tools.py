# tools.py
import logging
from typing import Dict, Any
from langchain_core.tools import tool
from mqtt_listener import get

def _nf(entity: str, key: Any) -> Dict[str, Any]:
    return {"found": False, "error": f"{entity} '{key}' not found"}

# box pose
@tool(args_schema={"box_id": int})
def find_box(box_id: int):
    """Return pose of the box with given id."""
    env = get("/inventory/boxes")
    logging.info("find_box(%s)  → snapshot %s", box_id, "HIT" if env else "MISS")

    if not env:
        return _nf("box", box_id)
    for b in env.data["items"]:
        if b["id"] == box_id:
            return {"found": True, **b}
    return _nf("box", box_id)

#module pose
@tool(args_schema={"namespace": str})
def find_module(namespace: str):
    """Return pose of a module by namespace."""
    env = get("/system/modules")
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
    env = get("/inventory/boxes")
    logging.info("find_box_by_color(%s) → snapshot %s", color, "HIT" if env else "MISS")

    if not env:
        return _nf("box", color)

    matches = [b for b in env.data["items"] if b["color"].lower() == color.lower()]
    if not matches:
        return _nf("box", color)

    return {"found": True, **matches[0]}



ALL_TOOLS = [find_box, find_box_by_color, find_module]

