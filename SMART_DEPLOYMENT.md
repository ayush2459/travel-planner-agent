# Deployment

For the full v2 setup and acceptance checklist, read [`SMART_UPGRADE_GUIDE.md`](SMART_UPGRADE_GUIDE.md).

## Local Windows

```cmd
python -m venv .venv
".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
copy .env.example.ollama .env
ollama list
".\.venv\Scripts\python.exe" -m py_compile app.py travel_planner\agent.py travel_planner\trip_store.py travel_planner\travel_tools.py travel_planner\budget.py travel_planner\itinerary.py
".\.venv\Scripts\python.exe" test_conversation_memory.py
".\.venv\Scripts\python.exe" test_upgrade_features.py
".\.venv\Scripts\python.exe" -m streamlit run app.py
```

## Render

- `LLM_PROVIDER=groq`
- `GROQ_MODEL=openai/gpt-oss-20b`
- `GROQ_API_KEY` stored only in Render Environment settings
- For durable trip data, attach managed PostgreSQL and set `DATABASE_URL` to its connection string. Without it, SQLite is used and the Render filesystem is not durable.

Never commit `.env`, API keys, the local `.venv`, or `travel_planner.db`.
