# main.py
"""
Main entry point for the warehouse assistant chat loop.
Continuously accepts user input, routes it through the LangGraph agent,
and prints the assistant's response.
"""

from langchain_core.messages import HumanMessage
from agent import agent
import mqtt_listener  # ensures MQTT listener is running

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
