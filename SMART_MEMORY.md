# Smart Conversation Memory Upgrade

This version makes the Travel Planner Agent conversation-aware.

## What changed

- The current Streamlit session keeps the complete chat history.
- `travel_planner/conversation_memory.py` normalizes and formats recent messages.
- `travel_planner.agent.ask_agent()` now receives conversation history.
- Groq and Ollama both receive the relevant previous conversation before the latest request.
- The system prompt explicitly preserves destination, days, budget, travellers, interests, dietary restrictions and previous itinerary decisions.
- Later corrections override earlier trip facts.
- Long conversations are bounded to avoid unbounded prompt growth.
- Live web fact-checking remains enabled.
- PDF reports and the existing UI remain supported.

## Example

User: `Plan 3 days in Jaipur for ₹15,000. I like history and local food.`

User: `Make day 2 cheaper.`

The second request is interpreted using the Jaipur/3-day/₹15,000 context rather than as a new unrelated request.

## Scope

This is **session memory**: it remembers the current conversation while the Streamlit session is alive.

It is intentionally not a permanent database yet. Persistent cross-session memory should be added later using PostgreSQL/Redis or another durable store rather than relying on Render's local filesystem.

## Test

From the project root:

```bash
python test_conversation_memory.py
```

Expected:

```text
Conversation memory smoke test: PASS
```
