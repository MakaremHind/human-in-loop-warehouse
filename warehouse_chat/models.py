# models.py
from typing import List, Literal, Dict, Any
from pydantic import BaseModel

# pose
class Pose(BaseModel):
    x: float; y: float; z: float
    roll: float; pitch: float; yaw: float

# items
class Box(BaseModel):
    id: int
    color: str
    kind: str              # "big_box" | "small_box"
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

# envelope
class Envelope(BaseModel):
    header: Dict[str, Any]
    type: Literal["BoxArray", "FiducialArray", "ModulePoseArray", "RegionArray"]
    data: Dict[str, List[Any]]          # always {"items": [...]}

# normaliser helper
def normalize_message(raw: Dict) -> Envelope:
    """Convert *any* of the four legacy shapes into the canonical Envelope."""
    env: Dict[str, Any] = {"header": raw["header"]}

    if "boxes" in raw:
        env["type"] = "BoxArray"
        env["data"] = {"items": [
            {"id": b["id"],
             "color": b["color"],
             "kind": b["type"],
             "pose": b["global_pose"]}
            for b in raw["boxes"]
        ]}
    elif "fiducials" in raw:
        env["type"] = "FiducialArray"
        env["data"] = {"items": [
            {"id": f["id"],
             "type": f["type"],
             "pose": f["relative_pose"]}
            for f in raw["fiducials"]
        ]}
    elif "modules" in raw:
        env["type"] = "ModulePoseArray"
        env["data"] = {"items": raw["modules"]}
    elif "map" in raw:
        env["type"] = "RegionArray"
        env["data"] = {"items": [
            {"top_corner": r["TopCorner"],
             "bottom_corner": r["BottomCorner"],
             "height": r["height"]}
            for r in raw["map"]
        ]}
    else:
        raise ValueError("Unrecognised message format")

    return Envelope.model_validate(env)
