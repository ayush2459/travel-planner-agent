from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from pdf_report import build_itinerary_pdf, looks_like_itinerary, suggest_filename
from travel_planner.agent import ask_agent, friendly_error, model_state

st.set_page_config(
    page_title="Travel Planner Agent",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Premium dark UI — deliberately targets the chat-input ancestor wrappers so
# Streamlit cannot leave the old white footer/background visible.
# ---------------------------------------------------------------------------
st.markdown(r"""
<style>
html, body, #root, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"],
main,
section,
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stBottomBlockContainer"] > div,
[data-testid="stBottomBlockContainer"] > div > div {
  background:#070a0f !important;
  color:#edf3f5 !important;
}
body { overflow-x:hidden; }
[data-testid="stHeader"] { background:rgba(7,10,15,.96) !important; }
.block-container { max-width:1450px; padding-top:1.7rem; padding-bottom:9rem !important; }
[data-testid="stSidebar"] {
  background:#090d13 !important; border-right:1px solid rgba(255,255,255,.08) !important;
}
[data-testid="stSidebar"] * { color:#dce5e9; }
[data-testid="stSidebar"] .stButton > button {
  background:rgba(255,255,255,.025) !important; color:#eaf0f2 !important;
  border:1px solid rgba(255,255,255,.07) !important;
}
[data-testid="stSidebar"] .stButton > button:hover { border-color:#69f0c0 !important; color:#69f0c0 !important; }
[data-testid="stChatMessage"] {
  border:1px solid rgba(255,255,255,.075) !important; border-radius:16px !important;
  background:#0d1419 !important; margin-bottom:12px !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { color:#e8eff2 !important; }
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div,
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] button {
  background:#0d1419 !important; color:#f4f7f8 !important;
}
[data-testid="stChatInput"] {
  border:1px solid #26343b !important; border-radius:16px !important;
  box-shadow:0 12px 40px rgba(0,0,0,.35) !important;
}
[data-testid="stChatInput"] textarea::placeholder { color:#71808a !important; }
[data-testid="stBottomBlockContainer"] { background:#070a0f !important; }
section[data-testid="stBottom"] { background:#070a0f !important; }
div:has(> [data-testid="stChatInput"]),
div:has([data-testid="stChatInput"]) { background:#070a0f !important; }
[data-testid="stAppViewContainer"] > .main { background:#070a0f !important; }
.hero {
  position:relative; overflow:hidden; padding:42px 44px; border:1px solid rgba(255,255,255,.09);
  border-radius:28px; background:radial-gradient(circle at 90% 0%,rgba(105,240,192,.12),transparent 32%),linear-gradient(135deg,#111821,#0a0e14);
  box-shadow:0 20px 60px rgba(0,0,0,.34); margin-bottom:24px;
}
.eyebrow { color:#69f0c0; font-size:.76rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; margin-bottom:10px; }
.hero h1 { font-size:clamp(2.2rem,5vw,4.4rem); line-height:.98; letter-spacing:-.055em; margin:0 0 16px; color:#f7f9fa; }
.hero p { color:#aeb9c2; font-size:1.05rem; line-height:1.7; max-width:760px; margin:0; }
.pill,.status { display:inline-block; padding:7px 11px; border:1px solid rgba(105,240,192,.18); border-radius:999px; background:rgba(105,240,192,.05); color:#69f0c0; font-size:.72rem; font-weight:700; }
.pill { margin-top:20px; }
.brand { color:#eaf0f2; font-size:1.25rem; font-weight:800; letter-spacing:.02em; }
.brand span { color:#69f0c0; }
.side-caption { color:#84919a; font-size:.78rem; line-height:1.55; margin:7px 0 16px; }
.model-card { padding:12px 13px; margin-top:14px; border-radius:14px; background:#0d1419; border:1px solid rgba(255,255,255,.07); }
.model-label { color:#71808a; font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; }
.model-value { color:#eaf0f2; font-size:.86rem; margin-top:3px; word-break:break-word; }
.report-card { margin:8px 0 18px; padding:10px 12px; border-radius:14px; border:1px solid rgba(105,240,192,.14); background:rgba(105,240,192,.035); }
.small-muted { color:#8a99a2; font-size:.74rem; }
div.stDownloadButton > button { background:linear-gradient(135deg,#69f0c0,#45cda2) !important; color:#07100d !important; border:0 !important; font-weight:800 !important; border-radius:10px !important; }
div[data-testid="stAlert"] { background:#10181d !important; }
</style>
""", unsafe_allow_html=True)

EXAMPLES = [
    "I want to visit Jaipur for 3 days with a budget of ₹15,000. I like history and local food.",
    "Plan a 7 day trip to Paris. I like art, history and food.",
    "4 days in Goa for 2 people with ₹20,000. We want beaches and some history.",
]

state = model_state()

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "messages" not in st.session_state:
    st.session_state.messages = []
if "queued" not in st.session_state:
    st.session_state.queued = None

def make_pdf(content: str, meta: dict) -> bytes:
    return build_itinerary_pdf(content, meta or {})

def render_pdf_button(index: int, message: dict):
    if not looks_like_itinerary(message.get("content", "")):
        return
    try:
        data = make_pdf(message["content"], message.get("meta") or {})
        st.markdown('<div class="report-card"><span class="small-muted">TRIP REPORT READY</span></div>', unsafe_allow_html=True)
        st.download_button(
            "⬇️ Download Trip Report (PDF)",
            data=data,
            file_name=suggest_filename(message["content"], message.get("meta") or {}),
            mime="application/pdf",
            key=f"pdf_{index}",
            use_container_width=False,
        )
    except Exception as exc:
        st.caption(f"PDF could not be created: {exc}")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero">
  <div class="eyebrow">AI TRAVEL STUDIO</div>
  <h1>Plan less.<br>Explore more.</h1>
  <p>Build a practical, budget-aware itinerary for your next trip. Tell the planner where you want to go, how long you have, who is travelling, and what you want to spend.</p>
  <div class="pill">✦ Powered by local Ollama · No Gemini generation quota</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="brand">TRAVEL<span>AI</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="side-caption">Your intelligent trip companion for routes, budgets, stays and day-by-day plans.</div>', unsafe_allow_html=True)
    st.markdown('<div class="status">✓ CONVERSATION MEMORY</div>', unsafe_allow_html=True)
    st.markdown('<div class="status" style="margin-left:4px">✓ PDF REPORTS</div>', unsafe_allow_html=True)

    st.markdown('<div class="model-card">', unsafe_allow_html=True)
    st.markdown('<div class="model-label">Model</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="model-value">{state["model"]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="model-label" style="margin-top:9px">Fallback</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="model-value">{", ".join(state["fallbacks"])}</div>', unsafe_allow_html=True)
    st.markdown('<div class="model-label" style="margin-top:9px">Endpoint</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="model-value">{state["api_base"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("")
    st.subheader("Try an example")
    for n, example in enumerate(EXAMPLES):
        if st.button(example, key=f"ex_{n}", use_container_width=True):
            st.session_state.queued = example
    st.divider()
    if st.button("＋ Start a new trip", use_container_width=True):
        st.session_state.session_id = uuid.uuid4().hex
        st.session_state.messages = []
        st.session_state.queued = None
        st.rerun()
    st.markdown(
        '<div class="small-muted">✓ CONVERSATION MEMORY — remembers the current trip across follow-up messages.<br>✓ LIVE FACT-CHECK GUARD — searches current web results before planning and asks the model to prefer official sources for time-sensitive claims.</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Chat history + PDF report buttons
# ---------------------------------------------------------------------------
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            meta = msg.get("meta") or {}
            if meta.get("web_search") == "live_search_ok":
                with st.expander("🔎 Fact-check sources used", expanded=False):
                    for src in (meta.get("web_sources") or [])[:6]:
                        if src.get("url"):
                            st.markdown(f"**{src.get('title','Source')}**  \\n{src['url']}\\n\\n{src.get('snippet','')}")
            render_pdf_button(i, msg)

prompt = st.chat_input("e.g. 3 days in Jaipur, budget ₹15,000, I like history and food") or st.session_state.queued
st.session_state.queued = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Planning your trip with Ollama..."):
            try:
                answer, meta = ask_agent(
                    prompt,
                    st.session_state.session_id,
                    history=st.session_state.messages,
                )
                if not answer:
                    answer = "Sorry, I did not get a response. Please try again."
                    meta = {}
            except Exception as exc:
                answer, meta = friendly_error(exc), {}

        st.markdown(answer)
        if meta.get("web_search") == "live_search_ok":
            with st.expander("🔎 Fact-check sources used", expanded=False):
                shown = meta.get("web_sources") or []
                for src in shown[:6]:
                    if src.get("url"):
                        st.markdown(f"**{src.get('title','Source')}**  \\n{src['url']}\\n\\n{src.get('snippet','')}")
        elif meta.get("web_search") == "live_search_unavailable":
            st.caption("⚠️ Live fact-check search was unavailable for this response; verify time-sensitive details from official sources.")
        render_pdf_button(len(st.session_state.messages), {"content": answer, "meta": meta})

    st.session_state.messages.append({"role": "assistant", "content": answer, "meta": meta})
    st.rerun()
