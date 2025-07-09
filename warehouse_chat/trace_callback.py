# trace_callback.py
# -----------------------------------------------------------------------------
# Gradio Trace Callback Handler for Warehouse Chatbot
# -----------------------------------------------------------------------------
# This module provides a callback handler for streaming agent reasoning steps
# to the Gradio UI. It updates the checklist state and pushes updates to the UI.
# All logic is preserved as in the original code.
# -----------------------------------------------------------------------------

from langchain.callbacks.base import BaseCallbackHandler
from checklist_state import ChecklistState
import json, textwrap 

class GradioTraceHandler(BaseCallbackHandler):
    """
    Callback handler for streaming agent trace steps to Gradio UI.
    Updates the checklist state and pushes updates via the provided push_fn.
    """
    def __init__(self, push_fn, checklist_state):
        super().__init__()
        self.push_fn = push_fn
        self.checklist = checklist_state

    def on_chain_start(self, *args, **kwargs):
        """Called at the start of a new agent chain."""
        self.checklist.add("☑ Entering new AgentExecutor chain")
        print(self.checklist.render())  # ✅ debug output
        self.push_fn(self.checklist.render())

    def on_agent_action(self, action, **kwargs):
        """Called when the agent takes an action (tool call)."""
        self.checklist.add(f"🔁 Loop {self.checklist.loop_count + 1}")
        self.checklist.add("🧠 Think", indent=1)
        self.checklist.add(f"🛠 Action: {action.tool}", indent=1)
        print(self.checklist.render())  # ✅ debug output
        self.push_fn(self.checklist.render())

    def on_tool_end(self, output, **kwargs):
        """
        Called when a tool returns output.
        Adds an observation and pretty-prints the output in the checklist.
        """
        self.checklist.add("🔎 Observation", indent=1)
        # Pretty-print output (dict/list as JSON, else str)
        if isinstance(output, (dict, list)):
            pretty = json.dumps(output, indent=2)
        else:
            pretty = str(output)
        # Limit each line to 100 chars for UI readability
        for line in textwrap.wrap(pretty, width=100,
                                  break_long_words=False,
                                  replace_whitespace=False):
            self.checklist.add(f"‣ {line}", indent=2, icon="")
        # Send the whole updated trace to Gradio
        self.push_fn(self.checklist.render())

    def on_chain_end(self, outputs, **kwargs):
        """Called at the end of the agent chain. Sets final answer and marks finished."""
        self.checklist.set_final_answer(outputs.get("output", "[no answer]"))
        self.checklist.mark_finished()
        print(self.checklist.render())
        self.push_fn(self.checklist.render())

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------
