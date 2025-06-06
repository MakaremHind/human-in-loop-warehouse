# Warehouse Assistant – LangGraph Agent

This project builds a conversational agent for monitoring and interacting with a modular warehouse system. It uses LangGraph for reasoning, MQTT for real-time data, and LangChain tools for querying the environment.

## What It Does

The assistant understands natural language and:

- Remembers past answers to avoid repeating tool calls
- Uses tools to fetch live MQTT data when needed
- Answers intelligently using past facts or current data
- Can track and report the most recent order in the system
- Can **trigger transport orders** (e.g. move a box from module A to B) and **await the result**
- Can **cancel an active transport order** using its correlation ID and suppress its final result

## Start the System

   ```bash
   # Start mock order handler (simulates execution)
   python mock_order_handler.py

   # Launch the assistant
   python main.py

   # Optional: publish test data
   python scripts/mock_order_generator.py
   python mock_broker_feeder.py
   ```


## Available Tools

| Tool                | Description                                          |
|---------------------|------------------------------------------------------|
| `find_box`          | Get full pose of a box by ID                         |
| `find_box_by_color` | Get pose of the first box with a given color         |
| `find_module`       | Get pose of a module by namespace                    |
| `list_boxes`        | List visible boxes (ID, color, kind only)            |
| `find_last_order`   | Retrieve the most recent completed transport order   |
| `trigger_order`     | Trigger a transport order and wait for the result    |
| `cancel_order`      | Cancel a transport order by correlation ID           |

## Behavior

- Uses `find_box` if a box's position is requested
- Uses `list_boxes` for a summary of visible boxes
- Uses `find_last_order` to check the latest order processed
- Uses trigger_order when asked to move a box from one module to another
- Avoids redundant tool use by reasoning from memory if the info was already retrieved
- Tracks the correlation ID and waits for a real MQTT response
- Uses cancel_order to stop an active transport and ignores the final result
- Automatically republish a success: false result when cancellation is requested


## How It Works

1. The system uses an Ollama-hosted LLM (`qwen3:latest` by default).
2. It tracks all user/agent messages in memory for reasoning.
3. It detects tool calls using patterns like:
   CALL find_box {"box_id": 3}
   CALL find_last_order()

4. The LLM chooses whether to call tools or answer from prior memory.
5. Background listeners publish transport results and suppressed canceled orders.

## Example Questions

- "Where is the box with ID 1?"
- "Is there any red box in the system?"
- "List all the boxes"
- "What was the last order executed?"
- “Move the box 1 from conveyor_02 to container_01”
- "Cancel the order with ID: abc123"



