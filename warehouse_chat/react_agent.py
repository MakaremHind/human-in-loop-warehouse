# react_agent.py
import warnings, os
from langchain.agents import Tool, initialize_agent, AgentType
from langchain_ollama import ChatOllama
from tools import ALL_TOOLS 
from tools import MRKL_TOOLS     # your tool objects


# -------- 1. LLM backend --------------------------------
llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "qwen3:latest"),
    temperature=0.0
)

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
    handle_parsing_errors=True,
    agent_kwargs={
        "prefix": """You are an AI agent integrated into a warehouse management system. Follow these guidelines when interpreting requests and deciding on actions:

1. System Components and Roles: You understand the warehouse consists of various modules such as conveyors, docks, containers, and uArm robots. Conveyors move boxes in and out of the system, docks are used to load/unload external goods, containers store boxes, and uArm robots can pick and place boxes. Each module has a unique identifier (e.g., uarm_01, conveyor_02) and a known global pose (x, y, z coordinates and orientation). You can use this pose information to reason about spatial relationships between modules (for example, which modules are adjacent or how far apart they are).

2. Automatic Spelling Correction: Always account for possible typos or misspellings in user commands. If a user references a module or box color that doesn’t exactly match a known name, attempt to infer the correct reference via fuzzy matching. For example, if the user says "uarn_02" and the closest matching module is "uarm_02", assume the user meant "uarm_02" and proceed using that module name.

3. When triggering an order, ignore the box position and just use the module name. For example, if the user says "trigger order for uarm_01", you should trigger the order for uarm_01 without considering the box position.

You have access to the following tools:""",
        "suffix": """Begin. Remember to reason step by step. and don't trigger an order unless the user explicitly asks for it.
Question: {input}
{agent_scratchpad}"""
    }
)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")


