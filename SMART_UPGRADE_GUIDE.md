# Travel Planner Agent — Smart Travel Suite v2

This package builds on the existing Streamlit + LiteLLM app. It is designed to be tested locally before any GitHub or Render deployment.

## Included improvements

- **Conversation-aware planning:** prior turns are passed to the model for follow-up edits. The current prompt is excluded from the prior-history context so it is not duplicated.
- **Saved trips:** trip messages are persisted in a database and can be reopened, deleted, and restored to earlier snapshots.
- **Storage options:** local runs default to SQLite (`travel_planner.db`); PostgreSQL is supported through `DATABASE_URL`.
- **Structured day view:** Markdown day sections are parsed into tabs. A user can ask the agent to revise one day while preserving the rest.
- **Budget worksheet:** deterministic category totals, limit comparison, and over-budget warning. User-entered values are estimates, not live prices.
- **Live weather lookup:** city geocoding and current conditions via Open-Meteo.
- **Currency conversion:** current reference rates via Frankfurter API, including the rate date.
- **Trip history:** changed saved states are snapshotted and can be restored from the sidebar.
- **Existing capabilities retained:** Groq on Render, Ollama locally, live web fact-check sources, dark UI, and PDF reports.
- **Evaluation:** `test_conversation_memory.py` and `test_upgrade_features.py`.

## Local Windows setup

Extract the ZIP, open CMD in the extracted `smart_work` folder, then run:

```cmd
python -m venv .venv
".\.venv\Scripts\python.exe" -m pip install --upgrade pip
".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
copy .env.example.ollama .env
ollama list
".\.venv\Scripts\python.exe" -m py_compile app.py travel_planner\agent.py travel_planner\trip_store.py travel_planner\travel_tools.py travel_planner\budget.py travel_planner\itinerary.py
".\.venv\Scripts\python.exe" test_conversation_memory.py
".\.venv\Scripts\python.exe" test_upgrade_features.py
".\.venv\Scripts\python.exe" -m streamlit run app.py
```

Use `http://localhost:8501`. `llama3.2:3b` should be installed and Ollama should be running. The local database is created automatically. Keep `.env`, `.venv`, and `travel_planner.db` out of Git.

## Saved trip access and privacy

The app adds a random `workspace` token to the URL so the same workspace can be reopened. Treat that URL as a private access link; do not share it. This is a lightweight single-user workspace, **not multi-user authentication**. Before offering public multi-user use, add sign-in, per-user authorization, CSRF/session controls, and database access tests.

## Persistent storage on Render

The Render free filesystem is ephemeral, so SQLite on Render is not durable across replacement/redeploy. For persistent hosted trips:

1. Create a managed PostgreSQL database.
2. Add its connection string as Render environment variable `DATABASE_URL` (use the provider's internal connection URL when the web service and database share the same Render region).
3. Keep `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-20b`, and set `GROQ_API_KEY` only in Render's environment settings.
4. Deploy only after local tests pass. Never put secrets in `.env.example`, code, or Git.

The database schema is created on app startup. For a larger production system, introduce formal schema migrations (Alembic), authenticated ownership, retention policies, and backups before real user data is stored.

## Live tools and factual limitations

- Open-Meteo provides weather conditions and geocoding; the result is not a guarantee of future weather.
- Frankfurter provides reference exchange rates; these are not bank/card rates and can lag markets.
- Web search is best-effort. If it fails, the UI warns that current facts need verification.
- Transport prices, booking inventory, visa eligibility, and attraction availability are not directly booked or guaranteed by this app.

## Local acceptance test

1. Start a trip: `Plan a 3-day trip to Jaipur for ₹15,000. I like history and local food.`
2. Ask: `Make day 2 cheaper.`
3. Ask: `I am vegetarian.`
4. Ask: `Replace day 3 with something historical.`
5. Refresh the page using the same workspace URL and confirm the saved trip appears.
6. Restore an earlier trip version from the sidebar.
7. Check weather for Jaipur and convert INR to USD.
8. Enter budget categories and confirm the calculator totals them independently of the model.
9. Download a PDF report.


## Update: shared budget context, report weather, and chat references

- Every chat turn receives a snapshot of the budget calculator (currency, category values, limit, total, and remaining amount). The agent should use these deterministic values for budget follow-ups instead of inventing arithmetic.
- When the itinerary destination can be inferred, the app fetches current conditions from Open-Meteo and displays the observation timestamp and local timezone. Responses are cached for five minutes to limit repeated calls. Weather is best-effort and requires an internet connection; it is a current-conditions snapshot, not a guarantee for future trip dates.
- PDF reports include a visual current-weather status panel and a category spend breakdown / budget comparison when calculator values are entered. Report generation refreshes weather within the five-minute cache window.
- The sidebar can select another saved conversation as optional context. The current trip's messages and current instructions take precedence over the reference trip.
- UI styles now explicitly set contrast for input controls, labels, tabs, tables, expanders, and responsive layouts to reduce invisible text and clipped Markdown tables.
- Acceptance checks include PDF generation with both weather and budget calculator metadata.


## Temperature visibility fix
Current weather is now fetched before the model response, included as trusted application context, and explicitly formatted in itinerary/planning answers. The chat weather line labels the temperature and apparent temperature. The PDF weather panel explicitly labels the temperature instead of showing only a bare number. If the weather API fails, the app must not invent a current temperature.
