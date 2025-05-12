# human-in-loop-warehouse
A LangGraph-powered LLM agent for natural language control of a modular material handling system using MQTT-based real-time data.

# `agent.py` – Final Version (Documented)

This file defines a memory-aware warehouse assistant agent using LangGraph and LangChain. It combines LLM-driven reasoning with explicit tool use for answering live queries about warehouse state.

---

## Key Features

- Supports memory-aware reasoning: Uses prior responses to reduce redundant tool calls
- Enforces correct tool usage: Ensures positional questions always use `find_box()`
- Includes flexible tools: ID, color, module, and list queries
- Based on LangGraph + Ollama LLM pipeline

---

## File Structure

### Configuration
```python
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:latest")
llm = ChatOllama(model=MODEL, temperature=0.0)
```

### Memory State Definition
```python
class Memory(TypedDict):
    messages: Annotated[list, add_messages]
```

---

## System Prompt

Instructs the LLM to either:
- Call a tool with a JSON payload
- Or reason from prior facts (recent tool outputs)

### Important Rules

- Use `find_box` for position (pose) lookups
- Use `list_boxes()` only for summaries
- Do not guess pose values

---

## LLM Node: `llm_node()`

Injects a system prompt and the last 5 non-tool assistant responses as context.

```python
response = llm.invoke([system_prompt, *state["messages"]])
```

---

## Tool Execution Node: `run_tool()`

Parses tool calls in format:
```text
CALL tool_name {"key": value}
```

Then:
- Finds the matching tool in `ALL_TOOLS`
- Invokes it with parsed arguments
- Formats the result for natural language output

Special handling for:
- `find_box` → returns full pose
- `list_boxes` → returns box summaries

---

## Routing: `route()`

Decides whether the LLM's message contains a tool call:
```python
return "tool" if CALL_RE.search(last) else "end"
```

---

## Graph Assembly

Creates a LangGraph with:
- Entry at `llm_node`
- Conditional edge to `run_tool`
- Exit after tool execution

```python
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", route)
graph.set_finish_point("tool")
agent = graph.compile()
```

---

## Summary

This version balances:
- Predictable tool usage
- Reasoned answers when appropriate
- Safety against hallucinations

You can now ask:
- “Where is the box with ID 3?”
- “Are there any small boxes?”
- “What boxes are visible?”

