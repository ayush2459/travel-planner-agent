# Travel Planner — Premium Dark UI

The included `app.py` keeps the existing agent, tools, Gemini model fallback/quota handling,
chat flow and PDF functionality while adding a premium dark travel UI.

Apply by overwriting the existing `app.py` with the included one.

Run:
```bash
source .venv/bin/activate
export TRAVEL_AGENT_MODEL=gemini-3.1-flash-lite
python -m streamlit run app.py
```

Do not copy a `.env` from this package.
