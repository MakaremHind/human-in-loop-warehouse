# app.py  ────────────────────────────────────────────────────────────────────
import gradio as gr
from react_agent import agent                    # your LangChain/LangGraph agent
from session_io  import (
    list_sessions, load_session, save_session, _new_id
)

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
#typing {font-style:italic; color:#666;}
"""

# ─────────────────────────── agent wrappers ───────────────────────────────
def agent_reply(user_msg: str, history: list):
    """Call the LangChain agent and append turns to the chat history."""
    reply = agent.invoke({"input": user_msg})["output"]
    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": reply})
    return history, history                      # (chatbot update, state update)

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

        # ── MAIN CHAT (right column) ─────────────────────────────────────
        with gr.Column(scale=1, min_width=600, elem_id="main-chat"):
            chatbot = gr.Chatbot(type="messages", height=600)
            state   = gr.State([])               # running conversation turns

            txt_in  = gr.Textbox(
                label="👤 You",
                placeholder="Ask me anything about your warehouse…"
            )

            typing = gr.Markdown("Assistant is typing…",
                                 visible=False, elem_id="typing")

            # interaction pipeline -----------------------------------------
            (
                txt_in.submit(lambda: gr.update(visible=True), None, typing,
                              show_progress=False)
                     .then(agent_reply, [txt_in, state],
                           [chatbot, state], show_progress="minimal")
                     .then(lambda: "", None, txt_in,    show_progress=False)
                     .then(lambda: gr.update(visible=False), None, typing,
                           show_progress=False)
                     .then(lambda: gr.update(visible=True),  None, save_btn,
                           show_progress=False)
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
