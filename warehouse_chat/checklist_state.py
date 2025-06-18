# checklist_state.py
class ChecklistState:
    def __init__(self):
        self.steps = []
        self.loop_count = 0
        self.final_answer = None
        self.finished = False

    def add(self, label, icon="☑", indent=0):
        self.steps.append({"label": label, "icon": icon, "indent": indent})

    def set_final_answer(self, answer):
        self.final_answer = answer

    def mark_finished(self):
        self.finished = True

    def render(self):
        lines = []
        for step in self.steps:
            pad = " " * step["indent"]
            lines.append(f'{pad}{step["icon"]} {step["label"]}')
        if self.final_answer:
            lines.append(f"\n✅ Final Answer")#:\n> {self.final_answer}")
        if self.finished:
            lines.append("\n🏁 Finished chain.")
        return "\n".join(lines)
    
