from __future__ import annotations

from collections.abc import Iterable

MAX_MESSAGES = 16
MAX_CONTEXT_CHARS = 12000


def normalize_history(history: Iterable[dict] | None) -> list[dict]:
    """Keep only safe chat fields needed by the LLM."""
    if not history:
        return []

    normalized = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        content = content.strip()
        if content:
            normalized.append({"role": role, "content": content})

    return normalized[-MAX_MESSAGES:]


def build_conversation_context(history: Iterable[dict] | None) -> str:
    """Format recent conversation history for the travel agent."""
    messages = normalize_history(history)
    if not messages:
        return ""

    lines = [
        "--- PREVIOUS CONVERSATION CONTEXT ---",
        "Use this conversation as context. Treat the latest user message as the current request.",
        "Preserve relevant trip facts and preferences unless the user explicitly changes them.",
    ]

    for message in messages:
        label = "USER" if message["role"] == "user" else "ASSISTANT"
        lines.append(f"{label}: {message['content']}")

    lines.append("--- END PREVIOUS CONVERSATION CONTEXT ---")
    text = "\n".join(lines)

    if len(text) <= MAX_CONTEXT_CHARS:
        return text

    # Keep the most recent context when a long conversation exceeds the limit.
    return (
        "--- PREVIOUS CONVERSATION CONTEXT ---\n"
        "Older messages were truncated. Prioritize the recent conversation below.\n"
        + text[-MAX_CONTEXT_CHARS:]
        + "\n--- END PREVIOUS CONVERSATION CONTEXT ---"
    )
