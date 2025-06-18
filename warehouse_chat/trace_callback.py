from langchain.callbacks.base import BaseCallbackHandler
from checklist_state import ChecklistState
import json, textwrap 

class GradioTraceHandler(BaseCallbackHandler):
    def __init__(self, push_fn, checklist_state):
        super().__init__()
        self.push_fn = push_fn
        self.checklist = checklist_state

    def on_chain_start(self, *args, **kwargs):
        self.checklist.add("☑ Entering new AgentExecutor chain")
        print(self.checklist.render())  # ✅ debug output
        self.push_fn(self.checklist.render())

    def on_agent_action(self, action, **kwargs):
        self.checklist.add(f"🔁 Loop {self.checklist.loop_count + 1}")
        self.checklist.add("🧠 Think", indent=1)
        self.checklist.add(f"🛠 Action: {action.tool}", indent=1)
        print(self.checklist.render())  # ✅ debug output
        self.push_fn(self.checklist.render())

    # trace_callback.py
    def on_tool_end(self, output, **kwargs):
            """
            `output` is whatever the tool returned.  We want to:
            ─ add the usual “🔎 Observation” bullet
            ─ pretty-print the output right underneath it
            ─ push the updated trace to the UI
            """
            self.checklist.add("🔎 Observation", indent=1)

            # ── NEW: dump the output itself ───────────────────────────────
            if isinstance(output, (dict, list)):
                pretty = json.dumps(output, indent=2)
            else:
                pretty = str(output)

            # limit each line to 100 chars so the accordion doesn’t scroll sideways
            for line in textwrap.wrap(pretty, width=100,
                                    break_long_words=False,
                                    replace_whitespace=False):
                self.checklist.add(f"‣ {line}", indent=2, icon="")

            # send the whole updated trace to Gradio
            self.push_fn(self.checklist.render())


    def on_chain_end(self, outputs, **kwargs):
        self.checklist.set_final_answer(outputs.get("output", "[no answer]"))
        self.checklist.mark_finished()
        print(self.checklist.render())
        self.push_fn(self.checklist.render())
