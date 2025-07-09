# agent.py
# -----------------------------------------------------------------------------
# FIRST DRAFT – NOT USED ANYMORE
# -----------------------------------------------------------------------------
# This file was an initial draft of the warehouse assistant agent using LangGraph.
# It is kept for reference only and is not used in the current system.
# All code below is commented for clarity and documentation purposes.
# -----------------------------------------------------------------------------

import os, re, json, logging
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_ollama import ChatOllama
from tools import ALL_TOOLS

# Set logging to error level to reduce noise
logging.getLogger().setLevel(logging.ERROR)

# Model selection from environment variable or default
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:latest")
llm = ChatOllama(model=MODEL, temperature=0.0)

# -----------------------------------------------------------------------------
# MEMORY TYPE for LangGraph state
# -----------------------------------------------------------------------------
class Memory(TypedDict):
    messages: Annotated[list, add_messages]

# -----------------------------------------------------------------------------
# BASE PROMPT for the agent
# -----------------------------------------------------------------------------
BASE_PROMPT = (
    "You are a warehouse assistant.\n"
    "You may either:\n"
    "- CALL a tool to retrieve live data (using JSON)\n"
    "- OR answer directly using what you remember from earlier turns\n\n"
    "Tool calls must follow this exact format:\n"
    "  CALL find_box {\"box_id\": 3}\n\n"
    "Available tools:\n"
    "- find_box(box_id:int)           → gives full pose\n"
    "- find_box_by_color(color:str)  → gives full pose\n"
    "- find_module(namespace:str)\n"
    "- list_boxes()                  → summary only (NO pose)\n"
    "- find_last_order()             → recent order summary\n"
    "- diagnose_failure()         → explain why the last order failed\n"
    "- trigger_order(start:str, goal:str, color:str, box_id:int)\n"
    "- cancel_order(correlation_id:str)  → stop awaiting a running transport\n\n"
    "If the user says: move box 3 from conveyor_02 to container_01,\n"
    "plan the needed tool calls and then execute them step by step.\n"
    "If you have no extra insight, just repeat the last observation as the answer.\n"
)

# -----------------------------------------------------------------------------
# LLM NODE: Handles LLM response generation
# -----------------------------------------------------------------------------
def llm_node(state: Memory) -> Memory:
    # Gather last 5 non-tool-call AI messages as context
    facts = [msg.content for msg in state["messages"] if isinstance(msg, AIMessage) and not msg.content.startswith("CALL")]
    system_prompt = AIMessage(role="system", content=BASE_PROMPT + "\n\nHere’s what you know so far:\n" + "\n".join(facts[-5:]))
    response = llm.invoke([system_prompt, *state["messages"]])
    return {"messages": state["messages"] + [response]}

# -----------------------------------------------------------------------------
# TOOL CALL REGEX: Pattern to extract tool calls from LLM output
# -----------------------------------------------------------------------------
CALL_RE = re.compile(r"\bCALL\s+(\w+)(?:\s+(\{[^{}]*\}))?", re.S)

# -----------------------------------------------------------------------------
# TOOL RUNNER: Executes the requested tool and formats the result
# -----------------------------------------------------------------------------
def run_tool(state: Memory) -> Memory:
    msg = state["messages"][-1].content
    match = CALL_RE.search(msg)
    if not match:
        return {"messages": state["messages"] + [AIMessage(content="Tool call not understood.")]}
    name, js = match.groups()
    args = json.loads(js) if js else {}
    # Find and invoke the tool by name
    for tool in ALL_TOOLS:
        if tool.name == name:
            result = tool.invoke(args)
            break
    else:
        return {"messages": state["messages"] + [AIMessage(content=f"Unknown tool `{name}`")]}
    logging.info("Tool '%s' result: %s", name, result)
    # Error case: tool did not find what was requested
    if isinstance(result, dict) and not result.get("found"):
        return {"messages": state["messages"] + [AIMessage(content=result.get("error", f"{name} failed."))]}
    # Format tool results for user
    if name in {"find_box", "find_box_by_color"}:
        pose = result["pose"]
        txt = (
            f"Box {result['id']} ({result['color']}, {result['kind']}) "
            f"is at x={pose['x']:.0f}, y={pose['y']:.0f}, z={pose['z']:.0f}."
        )
    elif name == "find_module":
        pose = result["pose"]
        txt = (
            f"🔧 Module `{result['namespace']}` is located at "
            f"x={pose['x']:.0f}, y={pose['y']:.0f}, z={pose['z']:.0f}."
        )
    elif name == "trigger_order":
        cid = result.get("correlation_id", "<unknown>")
        txt = (
            f"Order has been dispatched!\n"
            f"- ID: `{cid}`\n"
            f"- I’ll let you know when the result arrives."
        )
    elif name == "cancel_order":
        if result.get("found"):
            txt = (
                f"Order `{args.get('correlation_id')}` has been cancelled. "
                "I'll ignore its result if it comes in later."
            )
        else:
            txt = result.get("error", "Could not cancel the order.")
    elif name == "find_last_order":
        order = result["order"]
        txt = (
            "Last completed order:\n"
            f"- From: {order['starting_module']['namespace']}\n"
            f"- To:   {order['goal']['namespace']}\n"
            f"- Cargo: {order['cargo_box']['color']} {order['cargo_box']['type']} box "
            f"(ID {order['cargo_box']['id']})"
        )
    elif name == "diagnose_last_failure":
        txt = (f"Diagnosis of last failure:- Correlation ID: {result.get('correlation_id')} - Reason: {result.get('reason')}")
    else:
        txt = json.dumps(result)
    return {"messages": state["messages"] + [AIMessage(content=txt)]}

# -----------------------------------------------------------------------------
# PLANNER NODE: Generates a plan for tool calls
# -----------------------------------------------------------------------------
def planner_node(state: Memory) -> Memory:
    planner_prompt = AIMessage(role="system", content=BASE_PROMPT + "\n\nPlan your tool calls step-by-step.")
    response = llm.invoke([planner_prompt, *state["messages"]])
    return {"messages": state["messages"] + [response]}

# -----------------------------------------------------------------------------
# ROUTER: Determines the next node in the graph based on message content
# -----------------------------------------------------------------------------
def router(state: Memory) -> str:
    last = state["messages"][-1].content
    if "CALL" in last:
        return "tool"
    elif any(k in last.lower() for k in ["move box", "transfer box", "transport"]):
        return "planner"
    elif any(k in last.lower() for k in ["cancel order", "stop order"]):
        return "planner"
    elif any(k in last.lower() for k in ["diagnose", "reason", "why", "failed", "failure"]):
        return "planner"
    else:
        return "end"

# -----------------------------------------------------------------------------
# GRAPH DEFINITION: Sets up the LangGraph workflow
# -----------------------------------------------------------------------------
graph = StateGraph(Memory)
graph.add_node("llm", llm_node)
graph.add_node("tool", RunnableLambda(run_tool))
graph.add_node("planner", planner_node)
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", router)
graph.add_edge("planner", "llm")
graph.add_edge("tool", "llm")
graph.set_finish_point("tool")

agent = graph.compile()

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------