from travel_planner.conversation_memory import build_conversation_context, normalize_history

history = [
    {"role": "user", "content": "Plan 3 days in Jaipur for ₹15,000. I like history and local food."},
    {"role": "assistant", "content": "Here is your Jaipur itinerary."},
    {"role": "user", "content": "Make day 2 cheaper and keep the same trip."},
]

normalized = normalize_history(history)
assert len(normalized) == 3
context = build_conversation_context(history)
assert "Jaipur" in context
assert "₹15,000" in context
assert "Make day 2 cheaper" in context
assert "PREVIOUS CONVERSATION CONTEXT" in context
print("Conversation memory smoke test: PASS")
