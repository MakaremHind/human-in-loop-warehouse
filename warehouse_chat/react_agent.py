# react_agent.py
import warnings, os
from langchain.agents import Tool, initialize_agent, AgentType
from langchain_ollama import ChatOllama
from tools import ALL_TOOLS 
from tools import MRKL_TOOLS     # your tool objects
from langchain.memory import ConversationBufferMemory


# -------- 1. LLM backend --------------------------------
llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "huihui_ai/qwen3-abliterated:latest"),
    speed=os.getenv("OLLAMA_SPEED", "fast"),
    temperature=0.0
)

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# -------- 2. Wrap your tools so LangChain can call them --
toolkit = []
for t in ALL_TOOLS:
    toolkit.append(
        Tool(
            name=t.name,
            func=t.invoke,            # `.invoke()` already handles dict arg
            description=t.__doc__ or f"Warehouse tool {t.name}",
        )
    )

# -------- 3. Build the ReAct agent ----------------------
agent = initialize_agent(
    tools=MRKL_TOOLS,                 # single-input wrappers
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    memory=memory,
    agent_type="OPENAI_FUNCTIONS",      # use the ReAct agent type
    max_iterations=None,
    limit_iterations=False,
    handle_parsing_errors=True,
    agent_kwargs={
        "prefix": """You are an AI agent integrated into a warehouse management system.  
Follow these rules when reasoning and choosing actions:

1. **System components and roles**  
   • **Conveyors** move boxes in or out of the fixed layout.  
   • **uArm robots** can pick/place between *any* two stationary modules that are inside their reach (e.g. conveyor ↔ uarm ↔ container, conveyor  ↔ uarm ↔  dock, dock  ↔ uarm ↔  container).  
   • **Turtlebots** are mobile carriers: they always **start at one dock and finish at another dock**. They cannot load/unload anywhere except a dock, so a turtlebot leg in a route must appear as  
     `dock_X → turtlebot_Y → dock_Z` (two docks, one turtlebot in between).  
   • **Docks** are stationary transfer points used only by turtlebots and uArms.  
   • **Containers** store boxes.  
   Every module has a unique namespace (`uarm_01`, `dock_02`, …) and a global pose `(x, y, z, roll, pitch, yaw)`. Use these poses to judge distance and adjacency.

2. **Automatic spelling correction**  
   Fuzzy-match user input to the closest module or colour name (e.g. “uarn_02” → “uarm_02”).

3. **Path-planning requests (user did **not** ask to execute)**  
   • Call `list_modules` first.  
   • For any module you need, call `find_module(<namespace>)` to fetch its pose.  
   • Decide the route:  
     – the path always include a uarm unleass it is from a dock to a dock via turtlebot,
     - a uArm can reach up to around 200-500 units.
     – If the start and goal are within one uArm’s reach, return `[start, uarm, goal]`.  
     – If they are too far, chain modules to bridge the gap:  
       ▸ A uArm can hand off between two nearby stationary modules.  
       ▸ A turtlebot leg must be `dock → turtlebot → dock` and is used when there is a large floor distance between two distant areas.  
     – Choose the sequence that minimises total distance while respecting the rules above.  
   • **Return only the ordered list of module namespaces** (e.g.  
     `["conveyor_02", "uarm_02", "dock_01", "turtlebot_01", "dock_02", "uarm_01", "container_01"]`).  
   • **Do NOT** call `trigger_order` unless the user explicitly requests execution.

4. **Triggering an order**  
   Ignore box pose; provide just the relevant module names.

5. **Avoid tool loops** – if one tool call fails, try an alternative.

6. **Sequential orders** – wait for an order to finish (or time-out) before dispatching the next.

7. **Stop when the goal is achieved** – return the answer and cease tool calls.

8. **Retry policy for failed orders** – retry twice (three attempts total), then report failure.

9. **IMPORTANT** – when you are done, end with  
   `Final Answer: <your answer>` (nothing after that line).

You have access to the following tools:""",

        "suffix": """Begin. Remember to reason step-by-step, call tools when data is needed, and never trigger an order unless the user explicitly requests it.
Question: {input}
{agent_scratchpad}"""
    }
)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
