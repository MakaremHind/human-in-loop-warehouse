# session_io.py
import json, uuid, datetime, pathlib
SESS_DIR = pathlib.Path("chat_sessions")
SESS_DIR.mkdir(exist_ok=True)

def _new_id() -> str:
    ts = datetime.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    return f"{ts}_{uuid.uuid4().hex[:4]}"

def list_sessions():
    return sorted(p.stem for p in SESS_DIR.glob("*.json"))

def load_session(sess_id):
    file = SESS_DIR / f"{sess_id}.json"
    if file.exists():
        return json.loads(file.read_text())
    return []

def save_session(sess_id, history):
    file = SESS_DIR / f"{sess_id}.json"
    file.write_text(json.dumps(history, indent=2))
