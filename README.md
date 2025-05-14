# Warehouse Assistant – LangGraph Agent

This project builds a conversational agent for monitoring and interacting with a modular warehouse system. It uses LangGraph for reasoning, MQTT for real-time data, and LangChain tools for querying the environment.

## What It Does

The assistant understands natural language and:

* Remembers past answers to avoid repeating tool calls
* Uses tools to fetch live MQTT data when needed
* Answers intelligently using past facts or current data

## Available Tools

| Tool                | Description                                  |
| ------------------- | -------------------------------------------- |
| `find_box`          | Get full pose of a box by ID                 |
| `find_box_by_color` | Get pose of the first box with a given color |
| `find_module`       | Get pose of a module by namespace            |
| `list_boxes`        | List visible boxes (ID, color, kind only)    |

## Behavior

* Use `find_box` for box location questions.
* Use `list_boxes` for general inventory summaries.
* Answer directly if the info is already known.

## How It Works

1. The system uses an Ollama-hosted LLM (`qwen3:latest` by default).
2. It keeps track of messages (memory) for reasoning.
3. It parses tool calls using patterns like:

   ```
   CALL find_box {"box_id": 3}
   ```
4. It returns tool results as clear natural language responses.

## Example Questions

* "Where is the box with ID 1?"
* "Is there any red box in the system?"
* "List all the boxes"

This assistant combines real-time sensor integration with memory-aware AI to support a natural control interface for a warehouse system.
