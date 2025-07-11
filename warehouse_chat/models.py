# models.py
# -----------------------------------------------------------------------------
# Warehouse Data Models and Message Normalizer
# -----------------------------------------------------------------------------
# This module defines the Pydantic models for warehouse entities and provides
# a message normalization function for incoming raw data. All logic is preserved.
# -----------------------------------------------------------------------------

from typing import List, Literal, Dict, Any, Union
from pydantic import BaseModel
import json

# -----------------------------------------------------------------------------
# BASE TYPES
# -----------------------------------------------------------------------------
class Pose(BaseModel):
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float

# -----------------------------------------------------------------------------
# DATA ITEM TYPES
# -----------------------------------------------------------------------------
class Box(BaseModel):
    id: int
    color: str
    kind: str
    pose: Pose

class Fiducial(BaseModel):
    id: int
    type: Literal["aruco"]
    pose: Pose

class ModulePose(BaseModel):
    namespace: str
    pose: Pose

class Region(BaseModel):
    top_corner: Pose
    bottom_corner: Pose
    height: float

class OrderResult(BaseModel):
    starting_module: ModulePose
    goal: ModulePose
    cargo_box: Box

# -----------------------------------------------------------------------------
# ENVELOPE TYPE
# -----------------------------------------------------------------------------
class Envelope(BaseModel):
    header: Dict[str, Any]
    type: Literal["BoxArray", "FiducialArray", "ModulePoseArray", "RegionArray", "OrderResult"]
    data: Dict[str, Any]  # usually {"items": [...]}, or {"order": {...}} for orders

# -----------------------------------------------------------------------------
# MESSAGE NORMALIZER
# -----------------------------------------------------------------------------
def normalize_message(raw: Dict) -> Envelope:
    """
    Normalize a raw message dict into a standard Envelope object.
    Handles boxes, fiducials, modules, regions, and order results.
    """
    env: Dict[str, Any] = {"header": raw.get("header", {})}

    if "boxes" in raw:
        env["type"] = "BoxArray"
        env["data"] = {
            "boxes": [  # 🔄 use "boxes" instead of "items"
                {
                    "id": b["id"],
                    "color": b["color"],
                    "type": b["type"],           # keep "type" instead of "kind" to match original
                    "pose": b["global_pose"]
                }
                for b in raw["boxes"]
            ]
        }

    elif "fiducials" in raw:
        env["type"] = "FiducialArray"
        env["data"] = {
            "items": [
                {
                    "id": f["id"],
                    "type": f["type"],
                    "pose": f["relative_pose"]
                }
                for f in raw["fiducials"]
            ]
        }

    elif "modules" in raw:
        env["type"] = "ModulePoseArray"
        env["data"] = {"items": raw["modules"]}

    elif "map" in raw:
        env["type"] = "RegionArray"
        env["data"] = {
            "items": [
                {
                    "top_corner": r["TopCorner"],
                    "bottom_corner": r["BottomCorner"],
                    "height": r["height"]
                }
                for r in raw["map"]
            ]
        }

    elif "starting_module" in raw and "goal" in raw and "cargo_box" in raw:
        env["type"] = "OrderResult"
        env["data"] = {
            "order": {
                "starting_module": raw["starting_module"],
                "goal": raw["goal"],
                "cargo_box": raw["cargo_box"]
            }
        }

    elif "success" in raw and "info" in raw:
        raise ValueError("Order completion status message ignored.")

    else:
        raise ValueError("Unrecognised message format")

    return Envelope.model_validate(env)

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------