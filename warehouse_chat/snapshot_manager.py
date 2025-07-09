# snapshot_manager.py
# -----------------------------------------------------------------------------
# Warehouse Snapshot Manager
# -----------------------------------------------------------------------------
# This module provides a persistent snapshot store for MQTT and agent data.
# It loads, saves, and manages topic-based snapshots in a JSON file.
# All logic is preserved as in the original code.
# -----------------------------------------------------------------------------

import json
import os
from typing import Dict, Any

SNAPSHOT_FILE = "snapshot.json"

class SnapshotStore:
    """
    Persistent snapshot store for topic-based data.
    Loads from and saves to a JSON file on disk.
    """
    def __init__(self, path: str = SNAPSHOT_FILE):
        self.path = path
        self.snapshots: Dict[str, Any] = self._load_snapshots()

    def _load_snapshots(self) -> Dict[str, Any]:
        """Load snapshots from disk if file exists, else return empty dict."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[snapshot_manager] Failed to load snapshots: {e}")
        return {}

    def store(self, topic: str, message: Any):
        """Store a message under a topic and persist to disk."""
        self.snapshots[topic] = message
        self._save()

    def get(self, topic: str) -> Any:
        """Retrieve the last stored message for a topic."""
        return self.snapshots.get(topic)

    def _save(self):
        """Save all snapshots to disk."""
        try:
            with open(self.path, "w") as f:
                json.dump(self.snapshots, f, indent=2)
        except Exception as e:
            print(f"[snapshot_manager] Failed to save snapshot: {e}")

# Create a shared global instance
snapshot_store = SnapshotStore()

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------
