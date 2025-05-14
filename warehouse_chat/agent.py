# agent.py
import os, re, json, logging
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_ollama import ChatOllama
from tools import ALL_TOOLS

logging.getLogger().setLevel(logging.INFO)

MODEL = os.getenv("OLLAMA_MODEL", "qwen3:latest")
llm = ChatOllama(model=MODEL, temperature=0.0)

class Memory(TypedDict):
    messages: Annotated[list, add_messages]

# Updated instructions with reasoning + tool clarity
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
    "- list_boxes()                  → summary only (NO pose)\n\n"
    "If the user asks for a box's position, ALWAYS use find_box.\n"
    "Do NOT guess or use list_boxes for positions.\n"
    "Answer directly only if you already know the pose from earlier turns."
)

# ───────── LLM node ─────────
def llm_node(state: Memory) -> Memory:
    facts = []
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and not msg.content.strip().startswith("CALL "):
            facts.append(msg.content)

    context = BASE_PROMPT + "\n\nHere’s what you know so far:\n" + "\n".join(facts[-5:])
    system_prompt = AIMessage(role="system", content=context)
    response = llm.invoke([system_prompt, *state["messages"]])
    return {"messages": state["messages"] + [response]}


# Match tool calls, including tools with no arguments
CALL_RE = re.compile(r"\bCALL\s+(\w+)(?:\s+(\{[^{}]*\}))?", re.S)

# ───────── Tool runner node ─────────
def run_tool(state: Memory) -> Memory:
    msg = state["messages"][-1].content
    match = CALL_RE.search(msg)

    if not match:
        return {
            "messages": [AIMessage(
                content="Tool call not understood. Use JSON like: CALL find_box {\"box_id\": 3}"
            )]
        }

    name, js = match.groups()
    args = json.loads(js) if js else {}

    if name == "find_module" and "module_id" in args and "namespace" not in args:
        args["namespace"] = args.pop("module_id")

    for tool in ALL_TOOLS:
        if tool.name == name:
            result = tool.invoke(args)
            break
    else:
        return {"messages": [AIMessage(content=f"Unknown tool {name}")]}

    logging.info("🛠 Tool '%s' result: %s", name, result)

    if isinstance(result, dict) and not result.get("found"):
        txt = result["error"]

    elif name in {"find_box", "find_box_by_color"}:
        pose = result["pose"]
        txt = (f"Box {result['id']} ({result['color']}, {result['kind']}) "
               f"is at x = {pose['x']:.0f} mm, y = {pose['y']:.0f} mm, "
               f"z = {pose['z']:.0f} mm.")

    elif name == "find_module":
        pose = result["pose"]
        txt = (f"Module {result['namespace']} is at x = {pose['x']:.0f} mm, "
               f"y = {pose['y']:.0f} mm, z = {pose['z']:.0f} mm.")

    elif name == "list_boxes":
        if isinstance(result, list) and result:
            lines = [f"- Box {b['id']}: {b['color']} ({b['kind']})" for b in result]
            txt = "Currently visible boxes:\n" + "\n".join(lines)
            txt += "\n\nTo get exact position, use: CALL find_box {\"box_id\": N}"
        else:
            txt = "No boxes are currently visible."

    else:
        txt = json.dumps(result)

    return {"messages": state["messages"] + [AIMessage(content=txt)]}


# ───────── Decision logic ─────────
def route(state: Memory) -> str:
    last = state["messages"][-1].content
    return "tool" if CALL_RE.search(last) else "end"

# ───────── LangGraph wiring ─────────
graph = StateGraph(Memory)
graph.add_node("llm", llm_node)
graph.add_node("tool", RunnableLambda(run_tool))
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", route)
graph.set_finish_point("tool")


agent = graph.compile()
