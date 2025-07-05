# react_agent.py
import warnings, os
from langchain.agents import Tool, initialize_agent, AgentType
from langchain_ollama import ChatOllama
from tools import ALL_TOOLS 
from tools import MRKL_TOOLS     # your tool objects
from langchain.memory import ConversationBufferMemory


# -------- 1. LLM backend --------------------------------
llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "qwen3:latest"),
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
    max_iterations=None,
    limit_iterations=False,
    handle_parsing_errors=True,
    agent_kwargs = {
    # ------------ STATIC CONTEXT (prefix) ------------
    "prefix": """SYSTEM: You are “Warehouse-Bot”, an AI orchestrator for conveyors, uArm robots, turtlebots, docks and containers.

    **Module cheat-sheet**
    • Conveyors – move boxes into/out of the system and are the usual *start* point  
    • uArm – pick/place between any two stationary modules in reach  
    • Turtlebots – mobile carriers; always dock-to-dock  
    • Docks – transfer hubs for uArms & turtlebots (never allowed as start or goal)  
    • Containers – store boxes  

    Every module has a unique ID (e.g. `uarm_01`) and a pose `(x, y, z, roll, pitch, yaw)`—use this to judge reach and adjacency.
    
    
    **Rules**
    1. **No path planning** – output only `start_module → end_module`.  
    2. If the request is ambiguous, ask a clarifying question *before* any tool call.  
    3. **Retry** a failed tool call up to **2** extra times, then report failure in final answer. 
    4. Dispatch orders **sequentially**; wait for completion/timeout before the next.  
    5. Stop when the goal is met and write `Final Answer: <solution>`.  
    6. **Never use a dock** as `start` or `goal`; docks are for turtlebots only.  

    Fuzzy-match misspelled module or colour names.""",

        # ------------ HOW TO FORMAT TOOL CALLS ------------
        "format_instructions": """Use the ReAct loop **exactly** as shown:

    Thought: reflect on what to do  
    Action: one of [{tool_names}]  
    Action Input: JSON or plain text for the tool  
    Observation: tool output  
    (Repeat Thought / Action / Action Input / Observation as needed.)  
    Thought: I now know the final answer  
    Final Answer: <answer to user>

    Do **not** add any text outside this schema.
    Do **not** the same tool over and over again, use different tools in case if one tool did not worl.
    **Always** provide a final answer at the end of the conversation.

    ────────────────────────────────────────────────────────
    🛈  **trigger_order cheat-sheet**
    
    if the modules namespace are not provided, find the closest module to the start pose and use it as start module using find_closest_module tool then find the closest module to the goal pose and use it as goal module using  find_closest_module tool.
    
    ✅ *VALID* examples  
      • start=conveyor_02, goal=container_01, box_id=0  
      • start=container_01, goal=container_02, box_id=0  
      • start=conveyor_02, goal=container_01, box_color=green  
      • start=container_01, goal=container_02, box_color=red  

    ❌ *INVALID* examples (will raise errors)  
      • \"start\":\"container_01\",\"goal\":\"container_02\",\"box_id\":0,\"wait_timeout\":120   # timeout key ignored  
      • \"start\":\"dock_01\",\"goal\":\"container_02\",\"box_id\":0                          # dock used as start  
      • \"start\":\"container_01\",\"goal\":\"dock_01\",\"box_id\":0                          # dock used as goal  
      • \"start\":\"container_01\",\"goal\":\"container_02\",\"box_id\":\"red\"                 # box_id must be int  
      • \"start\":\"container_01\",\"goal\":\"container_02\",\"box_color\":0                  # box_color must be str

────────────────────────────────────────────────────────""",

        # ------------- DYNAMIC SUFFIX ---------------------
        "suffix": """Begin. Remember to reason step by step. and don't trigger an order unless the user explicitly asks for it and whem triggering an order don't look for a box or call find box function only the modules are matter.

    {chat_history}
    Question: {input}
    {agent_scratchpad}""",

        # ------------- SAFETY: HARD STOP ------------------
        "stop_sequence": ["Final Answer:"]
    }

)

#warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
