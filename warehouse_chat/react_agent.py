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
        "prefix": """You are a helpful warehouse assistant. Your job is to manage boxes, modules, orders, and logistics. 
You must use tools like list_boxes, find_box, and trigger_order to reason about the current inventory and execute user commands precisely.""",
        "suffix": """Begin. Remember to reason step by step. and don't trigger an order unless the user explicitly asks for it.
Question: {input}
{agent_scratchpad}"""
    }
)

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")


