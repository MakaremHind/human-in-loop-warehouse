# session_io.py
# -----------------------------------------------------------------------------
# Warehouse Chat Session I/O
# -----------------------------------------------------------------------------
# This module manages chat session storage and retrieval for the warehouse chatbot.
# It provides helpers for creating, listing, loading, and saving chat sessions.
# All logic is preserved as in the original code.
# -----------------------------------------------------------------------------

import json, uuid, datetime, pathlib

# Directory for storing chat session files
SESS_DIR = pathlib.Path("chat_sessions")
SESS_DIR.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# Generate a new unique session ID (timestamp + short UUID)
# -----------------------------------------------------------------------------
def _new_id() -> str:
    ts = datetime.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    return f"{ts}_{uuid.uuid4().hex[:4]}"

# -----------------------------------------------------------------------------
# List all available session IDs (sorted by name)
# -----------------------------------------------------------------------------
def list_sessions():
    return sorted(p.stem for p in SESS_DIR.glob("*.json"))

# -----------------------------------------------------------------------------
# Load a session's chat history by session ID
# -----------------------------------------------------------------------------
def load_session(sess_id):
    file = SESS_DIR / f"{sess_id}.json"
    if file.exists():
        return json.loads(file.read_text())
    return []

# -----------------------------------------------------------------------------
# Save a session's chat history by session ID
# -----------------------------------------------------------------------------
def save_session(sess_id, history):
    file = SESS_DIR / f"{sess_id}.json"
    file.write_text(json.dumps(history, indent=2))

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------
