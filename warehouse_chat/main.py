from langchain_core.messages import HumanMessage, AIMessage
from agent import agent
import mqtt_listener  # ensures MQTT listener is running
from tools import result_messages

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

    # ✅ Inject background result messages, if any
    while result_messages:
        result = result_messages.pop(0)
        summary = (
            f"✅ Order {result['correlation_id']} finished. "
            f"{'Success ✅' if result['success'] else 'Failed ❌'}."
        )
        print("Bot:", summary)
        chat_history.append(AIMessage(content=summary))
