from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from pdf_report import build_itinerary_pdf, looks_like_itinerary, suggest_filename
from travel_planner.agent import ask_agent, friendly_error, model_state
from travel_planner.trip_store import save_trip, list_trips, load_trip, delete_trip, storage_kind, list_revisions, load_revision
from travel_planner.travel_tools import current_weather, convert_currency, format_weather_summary
from travel_planner.budget import CATEGORIES, calculate_budget, compare_budget
from travel_planner.itinerary import extract_day_sections, parse_budget_table

st.set_page_config(
    page_title="Travel Planner Agent",
    page_icon="✈️",
    layout="wide",
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
div[data-testid="stAlert"] { background:#10181d !important; color:#edf3f5 !important; }
/* Keep Streamlit controls and data elements readable against the dark theme. */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li, [data-testid="stCaptionContainer"],
[data-testid="stExpander"] summary, [data-testid="stMetricLabel"],
[data-testid="stMetricValue"], [data-testid="stTab"] {
  color:#e6eef1 !important;
}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea {
  background:#111a20 !important; color:#f4f7f8 !important;
  border-color:#34444d !important;
}
[data-testid="stDataFrame"], [data-testid="stTable"] { color:#edf3f5 !important; }
[data-testid="stTabs"] button[role="tab"] { color:#b9c7cd !important; }
[data-testid="stTabs"] button[role="tab'][aria-selected="true"] { color:#69f0c0 !important; }
[data-testid="stExpander"] { border-color:#28363d !important; border-radius:12px !important; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] table { width:100%; }
[data-testid="stChatMessage"] table { display:block; max-width:100%; overflow-x:auto; border-collapse:collapse; }
[data-testid="stChatMessage"] th { background:#17232a !important; color:#69f0c0 !important; }
[data-testid="stChatMessage"] td, [data-testid="stChatMessage"] th { border-color:#34434b !important; padding:.45rem .6rem !important; }
button[kind="secondary"] { color:#e6eef1 !important; }
@media (max-width: 800px) {
  .block-container { padding-left:1rem; padding-right:1rem; padding-top:1rem; }
  .hero { padding:26px 22px; border-radius:20px; }
  .hero h1 { font-size:2.5rem; }
}
</style>
""", unsafe_allow_html=True)

EXAMPLES = [
    "I want to visit Jaipur for 3 days with a budget of ₹15,000. I like history and local food.",
    "Plan a 7 day trip to Paris. I like art, history and food.",
    "4 days in Goa for 2 people with ₹20,000. We want beaches and some history.",
]

state = model_state()

if "owner_id" not in st.session_state:
    # Workspace token in the URL lets the same user reopen saved trips later.
    # Treat this URL as private; anyone with it can access that workspace.
    workspace = st.query_params.get("workspace")
    if not workspace:
        workspace = uuid.uuid4().hex
        st.query_params["workspace"] = workspace
    st.session_state.owner_id = workspace
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "messages" not in st.session_state:
    st.session_state.messages = []
if "queued" not in st.session_state:
    st.session_state.queued = None

def make_pdf(content: str, meta: dict) -> bytes:
    return build_itinerary_pdf(content, meta or {})


def infer_trip_city(messages: list[dict]) -> str:
    patterns = [
        r"\b(?:trip|travel|holiday|vacation|visit|itinerary|plan(?: a trip)? to)\s+(?:to\s+)?([A-Z][A-Za-z.' -]{1,35}?)(?=\s+(?:for|with|on|in|under|budget|and|from)\b|[.,!?;]|$)",
        r"\b(?:in|around)\s+([A-Z][A-Za-z.' -]{1,35}?)\s+(?:for\s+\d+\s+days?|next|this|with\s+a\s+budget)",
    ]
    for message in messages:
        if message.get("role") != "user":
            continue
        text = str(message.get("content") or "")
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                city = match.group(1).strip(" .,-")
                if city and city.lower() not in {"a trip", "my trip", "the trip"}:
                    return city
    return ""


@st.cache_data(ttl=300, show_spinner=False)
def cached_current_weather(city: str) -> dict:
    return current_weather(city)


def budget_snapshot() -> dict:
    categories = {category: float(st.session_state.get(f"budget_{category}", 0.0) or 0.0) for category in CATEGORIES}
    currency = str(st.session_state.get("budget_currency", "INR"))
    limit = float(st.session_state.get("budget_limit", 15000.0) or 0.0)
    result = calculate_budget(categories)
    return {"categories": result["categories"], "total": result["total"], "limit": limit, "currency": currency}


def budget_context_text(snapshot: dict) -> str:
    entered = [f"- {name}: {value:,.2f} {snapshot['currency']}" for name, value in snapshot["categories"].items() if value > 0]
    rows = "\n".join(entered) if entered else "No expense categories have amounts entered yet."
    comparison = compare_budget(snapshot["total"], snapshot["limit"])
    status = "within budget" if comparison["within_budget"] else "over budget"
    return (
        "CURRENT BUDGET CALCULATOR STATE (authoritative arithmetic; use these values when answering budget questions):\n"
        f"Currency: {snapshot['currency']}\nBudget limit: {snapshot['limit']:,.2f} {snapshot['currency']}\n"
        f"Calculator total: {snapshot['total']:,.2f} {snapshot['currency']}\n"
        f"Remaining (limit minus total): {comparison['difference']:,.2f} {snapshot['currency']}\n"
        f"Status: {status}\nEntered categories:\n{rows}\n"
        "These are user-entered estimates, not verified live prices. Do not silently replace them with model estimates."
    )


def report_metadata(meta: dict | None, messages: list[dict]) -> dict:
    result = dict(meta or {})
    city = result.get("city") or infer_trip_city(messages)
    if city:
        result["city"] = city
        # Refresh the report's weather snapshot; cache limits repeated API calls to one per 5 minutes.
        try:
            result["weather"] = cached_current_weather(city)
            result.pop("weather_error", None)
        except Exception as exc:
            result["weather_error"] = str(exc)
    if not result.get("budget_calculator"):
        try:
            result["budget_calculator"] = budget_snapshot()
        except Exception:
            pass
    return result


def render_pdf_button(index: int, message: dict):
    if not looks_like_itinerary(message.get("content", "")):
        return
    try:
        message_meta = report_metadata(message.get("meta") or {}, st.session_state.messages[:index + 1])
        data = make_pdf(message["content"], message_meta)
        st.markdown('<div class="report-card"><span class="small-muted">TRIP REPORT READY</span></div>', unsafe_allow_html=True)
        st.download_button(
            "⬇️ Download Trip Report (PDF)",
            data=data,
            file_name=suggest_filename(message["content"], message_meta),
            mime="application/pdf",
            key=f"pdf_{index}",
            use_container_width=False,
        )
    except Exception as exc:
        st.caption(f"PDF could not be created: {exc}")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="hero">
  <div class="eyebrow">AI TRAVEL STUDIO · SMART SUITE</div>
  <h1>Plan less.<br>Explore more.</h1>
  <p>Build a practical, budget-aware itinerary for your next trip. Tell the planner where you want to go, how long you have, who is travelling, and what you want to spend.</p>
  <div class="pill">✦ Powered by {state['provider']} · Saved trips · Live travel tools</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
reference_history = []
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

    st.subheader("Saved trips")
    try:
        saved_trips = list_trips(st.session_state.owner_id)
        if saved_trips:
            trip_options = {f"{t['title']} · {t['updated_at'].strftime('%d %b %H:%M') if t['updated_at'] else ''}": t for t in saved_trips}
            selected_label = st.selectbox("Your trips", list(trip_options), key="saved_trip_select")
            selected_trip = trip_options[selected_label]
            c1, c2 = st.columns(2)
            if c1.button("Open trip", use_container_width=True):
                loaded = load_trip(st.session_state.owner_id, selected_trip["id"])
                if loaded is not None:
                    st.session_state.session_id = selected_trip["id"]
                    st.session_state.messages = loaded
                    st.rerun()
            if c2.button("Delete", use_container_width=True):
                if delete_trip(st.session_state.owner_id, selected_trip["id"]):
                    if st.session_state.session_id == selected_trip["id"]:
                        st.session_state.session_id = uuid.uuid4().hex
                        st.session_state.messages = []
                    st.success("Trip deleted")
                    st.rerun()
            revisions = list_revisions(st.session_state.owner_id, selected_trip["id"])
            if revisions:
                revision_labels = {f"Version · {r['created_at'].strftime('%d %b %Y %H:%M:%S') if r['created_at'] else 'unknown'} · {r['message_count']} messages": r for r in revisions}
                chosen_revision_label = st.selectbox("Trip history", list(revision_labels), key="trip_revision_select")
                if st.button("Restore selected version", use_container_width=True):
                    revision = revision_labels[chosen_revision_label]
                    restored = load_revision(st.session_state.owner_id, selected_trip["id"], revision["id"])
                    if restored is not None:
                        st.session_state.session_id = selected_trip["id"]
                        st.session_state.messages = restored
                        save_trip(st.session_state.owner_id, selected_trip["id"], restored)
                        st.rerun()
        else:
            st.caption("Your saved trips will appear here after your first reply.")
        reference_candidates = [t for t in saved_trips if t["id"] != st.session_state.session_id] if 'saved_trips' in locals() else []
        if reference_candidates:
            st.divider()
            st.caption("Use a previous chat as context for this trip")
            reference_options = {"No previous trip reference": None}
            for t in reference_candidates:
                label = f"{t['title']} · {t['updated_at'].strftime('%d %b %H:%M') if t['updated_at'] else ''}"
                reference_options[label] = t
            chosen_reference = st.selectbox("Reference a saved conversation", list(reference_options), key="reference_trip_select")
            reference_trip = reference_options[chosen_reference]
            if reference_trip:
                loaded_reference = load_trip(st.session_state.owner_id, reference_trip["id"])
                if loaded_reference:
                    reference_history = loaded_reference[-12:]
                    st.caption(f"Context enabled: {reference_trip['title']}")
        st.caption(f"Storage: {storage_kind()}")
    except Exception as store_exc:
        st.warning(f"Saved trips are unavailable: {store_exc}")

    with st.expander("Travel tools", expanded=False):
        st.caption("Live weather and currency rates require internet access.")
        weather_city = st.text_input("Weather for city", key="weather_city")
        if st.button("Check current weather", key="weather_button"):
            try:
                w = current_weather(weather_city)
                st.success(f"{w['place']}: {w.get('temperature_2m', '—')}°C, feels like {w.get('apparent_temperature', '—')}°C")
                st.caption(f"Humidity {w.get('relative_humidity_2m', '—')}% · Wind {w.get('wind_speed_10m', '—')} km/h · Local timezone {w.get('timezone', '—')}")
                st.caption("Current conditions from Open-Meteo; forecast details can change.")
            except Exception as tool_exc:
                st.error(f"Weather lookup failed: {tool_exc}")
        st.divider()
        amount = st.number_input("Amount", min_value=0.0, value=100.0, step=10.0, key="fx_amount")
        fx1, fx2 = st.columns(2)
        base_currency = fx1.selectbox("From", ["INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "THB"], key="fx_base")
        target_currency = fx2.selectbox("To", ["USD", "INR", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "THB"], index=0, key="fx_target")
        if st.button("Convert currency", key="fx_button"):
            try:
                fx = convert_currency(amount, base_currency, target_currency)
                st.success(f"{fx['amount']:,.2f} {fx['base']} = {fx['converted']:,.2f} {fx['target']}")
                st.caption(f"Rate date: {fx['date']} · 1 {fx['base']} = {fx['rate']:.6f} {fx['target']}")
            except Exception as tool_exc:
                st.error(f"Currency conversion failed: {tool_exc}")

    st.markdown(
        '<div class="small-muted">✓ Conversation memory · ✓ Saved trips · ✓ PDF reports · ✓ Live fact-checking</div>',
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
            weather = meta.get("weather")
            if weather:
                st.caption(
                    f"Current weather · {weather.get('place', meta.get('city', 'Destination'))}: "
                    f"{weather.get('weather_description', 'Conditions unavailable')} · "
                    f"{weather.get('temperature_2m', '—')}°C · refreshed {weather.get('time', 'time unavailable')} "
                    f"({weather.get('timezone', 'local time')})"
                )
            render_pdf_button(i, msg)

# Structured itinerary view: parse day headings so a traveller can inspect and revise one day.
latest_assistant = next((m for m in reversed(st.session_state.messages) if m.get("role") == "assistant"), None)
if latest_assistant:
    day_sections = extract_day_sections(latest_assistant.get("content", ""))
    if day_sections:
        with st.expander("Structured itinerary · edit a single day", expanded=False):
            tabs = st.tabs([d["heading"] for d in day_sections])
            for day_idx, (tab, day) in enumerate(zip(tabs, day_sections)):
                with tab:
                    st.markdown(day["body"] or "No details were parsed for this day.")
                    if st.button(f"Revise only {day['heading']}", key=f"revise_day_{st.session_state.session_id}_{day_idx}"):
                        st.session_state.queued = f"Revise only {day['heading']} of our current itinerary. Preserve the destination, budget, preferences, and all other days. Make the change coherent with the existing plan."
                        st.rerun()
            parsed_costs = parse_budget_table(latest_assistant.get("content", ""))
            if parsed_costs:
                st.caption("Budget rows detected in the generated plan (still estimates; use the calculator below for exact arithmetic).")
                st.dataframe(parsed_costs, use_container_width=True, hide_index=True)

prompt = st.chat_input("e.g. 3 days in Jaipur, budget ₹15,000, I like history and food") or st.session_state.queued
st.session_state.queued = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f"Planning your trip with {state['provider']}..."):
            try:
                snapshot = budget_snapshot()
                reference_context = ""
                if reference_history:
                    reference_context = "PREVIOUS SAVED TRIP REFERENCE (use only when relevant; current trip instructions take precedence):\n" + "\n".join(
                        f"{m.get('role', 'user').upper()}: {str(m.get('content', ''))[:1800]}" for m in reference_history
                    )
                city = infer_trip_city(st.session_state.messages)
                weather_snapshot = None
                weather_context = ""
                if city:
                    try:
                        weather_snapshot = cached_current_weather(city)
                        weather_context = (
                            "LIVE CURRENT WEATHER SNAPSHOT (verified API data; include a concise "
                            "Current Weather section in new itinerary/planning answers):\n"
                            + format_weather_summary(weather_snapshot)
                        )
                    except Exception as weather_exc:
                        # Keep planning available if the weather service is unavailable.
                        weather_context = (
                            f"Live weather lookup failed for {city}: {weather_exc}. "
                            "Do not invent current temperature or conditions."
                        )
                extra_context = budget_context_text(snapshot) + "\n\n" + reference_context
                if weather_context:
                    extra_context += "\n\n" + weather_context
                answer, meta = ask_agent(
                    prompt,
                    st.session_state.session_id,
                    history=st.session_state.messages[:-1],
                    additional_context=extra_context,
                )
                meta["budget_calculator"] = snapshot
                if city:
                    meta["city"] = city
                if weather_snapshot:
                    meta["weather"] = weather_snapshot
                    planning_request = any(term in prompt.lower() for term in (
                        "plan", "itinerary", "trip", "travel", "holiday", "vacation",
                        "visit", "day 1", "day 2", "day 3"
                    ))
                    if planning_request and "current weather" not in answer.lower() and "temperature:" not in answer.lower():
                        answer = answer.rstrip() + "\n\n### Current weather\n" + format_weather_summary(weather_snapshot)
                elif city and weather_context:
                    meta["weather_error"] = weather_context
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
        weather = meta.get("weather")
        if weather:
            st.caption(
                f"Current weather · {weather.get('place', meta.get('city', 'Destination'))}: "
                f"{weather.get('weather_description', 'Conditions unavailable')} · "
                f"Temperature: {weather.get('temperature_2m', 'unavailable')}°C · "
                f"feels like {weather.get('apparent_temperature', 'unavailable')}°C · "
                f"updated {weather.get('time', 'time unavailable')} "
                f"({weather.get('timezone', 'local time')})"
            )
        render_pdf_button(len(st.session_state.messages), {"content": answer, "meta": meta})

    st.session_state.messages.append({"role": "assistant", "content": answer, "meta": meta})
    try:
        save_trip(st.session_state.owner_id, st.session_state.session_id, st.session_state.messages)
    except Exception as store_exc:
        st.warning(f"Response was generated, but the trip could not be saved: {store_exc}")
    st.rerun()

# A deterministic budget worksheet: the total is calculated in Python, not by the LLM.
with st.expander("Budget calculator · verified arithmetic", expanded=False):
    st.caption("Enter estimates in your trip currency. These figures are user-entered estimates, not live quotes.")
    budget_currency = st.selectbox("Budget currency", ["INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "THB"], key="budget_currency")
    budget_values = {}
    cols = st.columns(3)
    for idx, category in enumerate(CATEGORIES):
        with cols[idx % 3]:
            budget_values[category] = st.number_input(category, min_value=0.0, value=0.0, step=500.0, key=f"budget_{category}")
    budget_limit = st.number_input("Your total budget limit", min_value=0.0, value=15000.0, step=1000.0, key="budget_limit")
    try:
        budget_result = calculate_budget(budget_values)
        comparison = compare_budget(budget_result["total"], budget_limit)
        b1, b2, b3 = st.columns(3)
        b1.metric("Estimated total", f"{budget_currency} {budget_result['total']:,.2f}")
        b2.metric("Budget limit", f"{budget_currency} {budget_limit:,.2f}")
        b3.metric("Remaining / over", f"{budget_currency} {comparison['difference']:,.2f}")
        if comparison["within_budget"]:
            st.success("Your entered estimates are within the budget.")
        else:
            st.error("Your entered estimates exceed the budget. Reduce costs or increase the limit.")
        nonzero = {k: v for k, v in budget_result["categories"].items() if v > 0}
        if nonzero:
            st.bar_chart({"Category": list(nonzero.keys()), "Amount": list(nonzero.values())}, x="Category", y="Amount", use_container_width=True)
        st.caption("The next chat message receives this calculator state automatically, including the total and remaining budget.")
    except ValueError as budget_exc:
        st.error(str(budget_exc))
