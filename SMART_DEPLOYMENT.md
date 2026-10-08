# Smart Memory Deployment Notes

## Local Windows

```cmd
cd /d "C:\Users\Ayush\Downloads\travel-planner-agent-main"
".\.venv\Scripts\python.exe" -m py_compile app.py travel_planner\agent.py travel_planner\conversation_memory.py
".\.venv\Scripts\python.exe" test_conversation_memory.py
streamlit run app.py
```

Use Ollama locally:

```env
LLM_PROVIDER=ollama
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

## Render

Keep the existing production variables:

```text
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=<stored only in Render>
```

No API key belongs in this ZIP or GitHub.

## Manual conversation test

1. `Plan a 3-day trip to Jaipur with a budget of ₹15,000. I like history and local food.`
2. `Make day 2 cheaper.`
3. `I am vegetarian.`
4. `Replace day 3 with something historical.`
5. `What is the total budget now?`

The agent should treat these as one trip and retain relevant facts.
