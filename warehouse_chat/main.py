# main.py
import mqtt_listener 
from langchain_core.messages import HumanMessage
from react_agent import agent             # <<< NEW IMPORT
from snapshot_manager import snapshot_store
import time, json

chat_history = []

print("[Chat] Type 'quit' to exit.")
while True:
    try:
        user_input = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[Chat] Exiting.")
        break

    if user_input.lower() in {"quit", "exit"}:
        print("[Chat] Goodbye!")
        break

    # --- run ReAct agent (no state object needed) ---------
    reply = agent.invoke({"input": user_input})["output"]
    print("Bot:", reply)
    chat_history.append((user_input, reply))

    # --- (optional) same watcher you had before ----------
    try:
        data = json.loads(reply)
        cid = data.get("correlation_id")
        if cid:
            print(f"[Watcher] Waiting for result of order ID {cid}…")
            for _ in range(20):
                snap = snapshot_store.get("base_01/order_request/response")
                if snap and snap.get("header", {}).get("correlation_id") == cid:
                    succ = snap.get("success", False)
                    print("Bot:", f"Order {cid} finished. {'Success' if succ else 'Failed'}.")
                    break
                time.sleep(1)
            else:
                print("Bot: Timed out waiting for order result.")
    except Exception:
        pass
