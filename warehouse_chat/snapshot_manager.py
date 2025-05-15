# snapshot_manager.py

import json
import os
from typing import Dict, Any

SNAPSHOT_FILE = "snapshot.json"

class SnapshotStore:
    def __init__(self, path: str = SNAPSHOT_FILE):
        self.path = path
        self.snapshots: Dict[str, Any] = self._load_snapshots()

    def _load_snapshots(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[snapshot_manager] Failed to load snapshots: {e}")
        return {}

    def store(self, topic: str, message: Any):
        self.snapshots[topic] = message
        self._save()

    def get(self, topic: str) -> Any:
        return self.snapshots.get(topic)

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.snapshots, f, indent=2)
        except Exception as e:
            print(f"[snapshot_manager] Failed to save snapshot: {e}")

# Create a shared global instance
snapshot_store = SnapshotStore()
