# app.py
# -----------------------------------------------------------------------------
# Warehouse Chatbot Gradio App
# -----------------------------------------------------------------------------
# This script launches the Gradio web UI for the warehouse chatbot, including
# session management, agent invocation, and UI layout. All logic is preserved.
# -----------------------------------------------------------------------------

# app.py  ────────────────────────────────────────────────────────────────────
import gradio as gr
from checklist_state import ChecklistState
from trace_callback import GradioTraceHandler
from langchain.callbacks import StdOutCallbackHandler
from react_agent import agent                    # your LangChain/LangGraph agent
from session_io  import (
    list_sessions, load_session, save_session, _new_id
)
import re
import io, contextlib



# ─────────────────────────── static assets ────────────────────────────────
LOGO_LEFT  = "assets/IFL.png"
LOGO_RIGHT = "assets/MMH_3.png"

custom_css = """
/* ─── corner logos ──────────────────────────────────────────────────── */
#logo-left  {position:absolute; top:10px; left:10px;  width:60px; height:60px;}
#logo-right {position:absolute; top:10px; right:10px; width:60px; height:60px;}
/* push title below the two logos */
#title {margin-top:80px;}
/* simple emphasis for typing banner */
/* blue Thoughts, violet Actions, green Observations */
#trace-md {
    font-family: ui-monospace, monospace;
    white-space: pre-wrap;
    max-height: 600px;      /* pick any height that looks good */
    overflow-y: auto;       /* ← gives you the scrollbar */
}
#trace-md span.thought      { color:#4682b4; }
#trace-md span.action       { color:#7d3c98; }
#trace-md span.observation  { color:#2e8b57; }
#trace-md {font-family:ui-monospace,monospace; white-space:pre-wrap;}
"""
# ─────────────────────────── agent wrappers ───────────────────────────────
def colourise(raw: str) -> str:
    raw = re.sub(r"^Thought:",      "<span class='thought'>Thought:</span>",      raw, flags=re.M)
    raw = re.sub(r"^Action:",       "<span class='action'>Action:</span>",       raw, flags=re.M)
    raw = re.sub(r"^Observation:",  "<span class='observation'>Observation:</span>",  raw, flags=re.M)
    return raw


# ─── agent wrappers ───────────────────────────────────────────────
def agent_reply(user_msg: str, history: list, checklist_state: ChecklistState):
    """Handles a user message, updates history, and streams agent output."""
    checklist_state.__init__()                          # reset
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": "…"})
    yield history, history, gr.update(value=checklist_state.render())

    updates = []

    def push(text: str):
        print("PUSH-CB:", text[:60].replace("\n", "⏎"))
        updates.append(gr.update(value=text))

    # ------------ THE ONLY CHANGE IS HERE ------------------
    reply = agent.invoke(
        {"input": user_msg},
        config={
            "callbacks": [
                StdOutCallbackHandler(),
                GradioTraceHandler(push, checklist_state),
            ]
        },
    )["output"]
    # -------------------------------------------------------

    for u in updates:
        yield history, history, u

    history[-1] = {"role": "assistant", "content": reply}
    yield history, history, gr.update(value=checklist_state.render())




# ── QUICK SELF-TEST ────────────────────────────────────────────────────────
# QUICK SELF-TEST ──────────────────────────────────────────────────────────
if False:  
    cs = ChecklistState()

    def push_test(text):
        print("PUSH-CB:", text[:60].replace("\n", "⏎"))

    h = GradioTraceHandler(push_test, cs)

    h.on_chain_start({}, {})
    h.on_agent_action(type("Dummy", (), {"tool": "test_tool"})(),
                      run_id="x")           # ← named kwarg
    h.on_tool_end("tool output", run_id="x") # ← named kwarg
    h.on_chain_end({"output": "final!"}, run_id="x")
    raise SystemExit("✅ handler self-test finished")



# ─────────────────────────── session helpers ──────────────────────────────
def new_chat(_, __):
    sess_id = _new_id()
    return (
        gr.update(value=sess_id, choices=list_sessions() + [sess_id]),
        [],          # clear chatbot
        []           # clear state
    )

def load_chat(sess_id):
    hist = load_session(sess_id)
    return hist, hist

def save_chat(sess_id, history):
    save_session(sess_id, history)
    return gr.update(visible=True)               # could show a toast instead

# ───────────────────────────── UI layout ──────────────────────────────────
with gr.Blocks(css=custom_css, theme=gr.themes.Soft()) as demo:
    # corner badges & title -------------------------------------------------
    gr.Image(LOGO_LEFT,  elem_id="logo-left",
             show_label=False, show_download_button=False,
             show_fullscreen_button=False)
    gr.Image(LOGO_RIGHT, elem_id="logo-right",
             show_label=False, show_download_button=False,
             show_fullscreen_button=False)
    gr.Markdown("# <center>WAREHOUSE CHATBOT</center>", elem_id="title")

    with gr.Row():                         # ➜ sidebar | main chat
        # ── SIDEBAR (left column) ─────────────────────────────────────────
        with gr.Column(scale=0, min_width=400, elem_id="sidebar"):
            session_dd = gr.Dropdown(
                label="✨ Chats", choices=list_sessions(), interactive=True
            )
            new_btn  = gr.Button("➕ New chat")
            save_btn = gr.Button("💾 Save", visible=False)
            
            #  fold-away area that will stream the reasoning steps
            with gr.Accordion("⚙️  Agent trace", open=True):
                trace_box  = gr.Markdown(value="Ready…", elem_id="trace-md")

        # ── MAIN CHAT (right column) ─────────────────────────────────────
        with gr.Column(scale=1, min_width=600, elem_id="main-chat"):
            chatbot = gr.Chatbot(type="messages", height=600)
            state   = gr.State([])               # running conversation turns
            state_checklist = gr.State(ChecklistState())

            txt_in  = gr.Textbox(
                label="👤 You",
                placeholder="Ask me anything about your warehouse…"
            )
            
            state_trace = gr.State([])

            # interaction pipeline -----------------------------------------
            (
                txt_in.submit(agent_reply,[txt_in, state, state_checklist],[chatbot, state, trace_box]) \
                .then(lambda: "", None, txt_in, show_progress=False) \
                .then(lambda: gr.update(visible=True), None, save_btn, show_progress=False)

            )

    # ─── side-effects (new / load / save)  outside the Row  ───────────────
    new_btn.click(new_chat, [new_btn, state],
                  [session_dd, chatbot, state])

    session_dd.change(load_chat, session_dd, [chatbot, state]) \
               .then(lambda: gr.update(visible=False), None, save_btn)

    save_btn.click(save_chat, [session_dd, state], save_btn)

# ─────────────────────────── run app ───────────────────────────────────────
if __name__ == "__main__":
    demo.launch()

# -----------------------------------------------------------------------------
# END OF FILE
# -----------------------------------------------------------------------------
