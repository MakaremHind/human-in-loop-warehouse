# main.py
from __future__ import annotations

import signal
import sys
import threading
import time
import json

import mqtt_listener  # noqa – imported for its side-effects (snapshot feed)
from react_agent import agent
from snapshot_manager import snapshot_store

# ────────────────────────────── graceful shutdown ─────────────────────────────
shutdown_event = threading.Event()


def _handle_sigint(signum: int, frame):  # noqa: D401 – simple callback
    """Handle Ctrl-C once and leave without a traceback."""
    print("\n[Chat]  Ctrl-C received – shutting down …")
    shutdown_event.set()

    # Optional: close MQTT sockets opened by background listeners
    try:
        mqtt_listener.client.disconnect()  # if your listener exposes the client
    except Exception:
        pass

    sys.exit(0)  # clean exit, return code 0


signal.signal(signal.SIGINT, _handle_sigint)

# ────────────────────────────── main REPL loop ────────────────────────────────
chat_history: list[tuple[str, str]] = []

print("[Chat] Type 'quit' to exit.")

while not shutdown_event.is_set():
    # ── read user input ───────────────────────────────────────────────────────
    try:
        user_input = input("You: ").strip()
    except EOFError:
        print("\n[Chat] Exiting.")
        break

    if not user_input:
        continue
    if user_input.lower() in {"quit", "exit"}:
        print("[Chat] Goodbye!")
        break

    # ── run ReAct agent ───────────────────────────────────────────────────────
    try:
        result = agent.invoke({"input": user_input})["output"]
    except KeyboardInterrupt:
        # If Ctrl-C arrived while the agent was busy, the SIGINT handler has
        # already set the flag; just break out of the loop.
        break

    # ── universal result-handler (dict OR string/list) ────────────────────────
    if isinstance(result, dict):
        # Pretty print if it contains a user-facing “message”
        print("Bot:", result.get("message", result))
        cid = result.get("correlation_id")
    else:
        # Plain string / list / whatever
        print("Bot:", result)
        # Best-effort: maybe it’s JSON in a string
        try:
            maybe_json = json.loads(result) if isinstance(result, str) else None
            cid = maybe_json.get("correlation_id") if isinstance(maybe_json, dict) else None
        except (json.JSONDecodeError, TypeError):
            cid = None

    chat_history.append((user_input, str(result)))

    # ── optional watcher that waits for order completion ──────────────────────
    if cid:
        print(f"[Watcher] Waiting for result of order ID {cid} …")
        # wait up to 20 s (interruptible by Ctrl-C)
        for _ in range(20):
            if shutdown_event.wait(1):          # wake early on Ctrl-C
                break
            snap = snapshot_store.get("base_01/order_request/response")
            if (
                snap
                and snap.get("header", {}).get("correlation_id") == cid
            ):
                succ = snap.get("success", False)
                print("Bot:", f"Order {cid} finished. {'Success' if succ else 'Failed'}.")
                break
        else:
            print("Bot: Timed out waiting for order result.")
