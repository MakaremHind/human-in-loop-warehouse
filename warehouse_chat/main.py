from langchain_core.messages import HumanMessage, AIMessage
from agent import agent
import mqtt_listener  # ensures MQTT listener is running
from snapshot_manager import snapshot_store
import time
import json

# Chat history persists through turns
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

    # Run agent with current input and conversation history
    state = agent.invoke({"messages": chat_history + [HumanMessage(content=user_input)]})
    reply = state["messages"][-1]
    print("Bot:", reply.content)

    # Save the latest turn
    chat_history.extend([HumanMessage(content=user_input), reply])

    # ⏳ Check for triggered order to watch for a result
    try:
        data = json.loads(reply.content)
        correlation_id = data.get("correlation_id")
        if correlation_id:
            print(f"[Watcher] Waiting for result of order ID {correlation_id}...")

            # Poll for up to 20 seconds
            for _ in range(20):
                snapshot = snapshot_store.get("base_01/order_request/response")
                if snapshot:
                    header = snapshot.get("header", {})
                    if header.get("correlation_id") == correlation_id:
                        success = snapshot.get("success", False)
                        result_msg = f"Order {correlation_id} finished. {' Success' if success else ' Failed'}."
                        print("Bot:", result_msg)
                        chat_history.append(AIMessage(content=result_msg))
                        break
                time.sleep(1)
            else:
                print("Bot: Timed out waiting for order result.")
    except Exception:
        pass  # Not a JSON trigger_order response
