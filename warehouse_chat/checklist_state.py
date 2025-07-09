# checklist_state.py
# -----------------------------------------------------------------------------
# Checklist State Helper for Warehouse Chatbot
# -----------------------------------------------------------------------------
# This class manages the step-by-step checklist state for the chatbot UI.
# It tracks steps, loop count, final answer, and finished status, and provides
# a render method for display. All logic is preserved as in the original code.
# -----------------------------------------------------------------------------

class ChecklistState:
    def __init__(self):
        # List of step dicts: {label, icon, indent}
        self.steps = []
        # Number of reasoning loops (if used)
        self.loop_count = 0
        # Final answer string (if set)
        self.final_answer = None
        # Whether the chain is finished
        self.finished = False

    def add(self, label, icon="☑", indent=0):
        """Add a step to the checklist with optional icon and indent."""
        self.steps.append({"label": label, "icon": icon, "indent": indent})

    def set_final_answer(self, answer):
        """Set the final answer for the checklist."""
        self.final_answer = answer

    def mark_finished(self):
        """Mark the checklist as finished."""
        self.finished = True

    def render(self):
        """Render the checklist as a formatted string for display."""
        lines = []
        for step in self.steps:
            pad = " " * step["indent"]
            lines.append(f'{pad}{step["icon"]} {step["label"]}')
        if self.final_answer:
            lines.append(f"\n✅ Final Answer")  #:
        if self.finished:
            lines.append("\n🏁 Finished chain.")
        return "\n".join(lines)

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------

