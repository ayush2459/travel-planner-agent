# Travel Planner — Ollama + PDF Report

This build uses local Ollama through LiteLLM. It does not require a Gemini API key.

## `.env`
```env
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_FALLBACK_MODELS=llama3.2:3b
```

Older `TRAVEL_AGENT_MODEL` / `TRAVEL_AGENT_FALLBACKS` are also accepted. If an old
Gemini model remains in those variables, this Ollama build intentionally ignores
the Gemini model and uses `llama3.1:8b`.

## Install
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Verify
```bash
ollama list
python -m py_compile app.py travel_planner/agent.py pdf_report.py
```

## Run
```bash
python -m streamlit run app.py
```

Every itinerary following the standard report structure gets a **Download Trip
Report (PDF)** button. The PDF uses the project's original styled report generator
with summary, budget visualization, day-by-day sections and tips.
