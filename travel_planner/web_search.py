"""Live web search used as a fact-check guard for the local Ollama agent.

Uses the public DuckDuckGo search endpoint through the `ddgs` package, so no
Google/Gemini generation quota or API key is required. Search results are
passed to Ollama as evidence; the model is instructed not to claim verification
when evidence is missing.
"""
from __future__ import annotations

import re
from typing import Any

def _clean(text: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]

def search_web(query: str, max_results: int = 6) -> list[dict[str, str]]:
    try:
        from ddgs import DDGS
    except Exception as exc:
        return [{"error": f"Web search dependency unavailable: {exc}"}]

    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                title = _clean(item.get("title", ""), 180)
                url = _clean(item.get("href", "") or item.get("url", ""), 500)
                body = _clean(item.get("body", "") or item.get("snippet", ""), 800)
                if title and url:
                    results.append({"title": title, "url": url, "snippet": body})
    except Exception as exc:
        return [{"error": f"Live web search failed: {exc}"}]
    return results

def format_sources(results: list[dict[str, str]]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        if "error" in r:
            lines.append(f"[Search status] {r['error']}")
        else:
            lines.append(f"[{i}] {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}")
    return "\n\n".join(lines)

def is_time_sensitive(prompt: str) -> bool:
    p = prompt.lower()
    keywords = (
        "opening", "open", "closed", "closure", "ticket", "price", "visa",
        "passport", "entry", "permit", "current", "today", "this week",
        "event", "festival", "weather", "transport", "train", "flight",
        "bus", "metro", "availability", "booking", "reservation", "hours",
        "timing", "schedule", "safe", "safety", "rule", "rules",
    )
    return any(k in p for k in keywords)

def build_search_query(prompt: str) -> str:
    # Search the user's actual request, plus official/current context.
    p = re.sub(r"\s+", " ", prompt).strip()
    suffix = " official tourism current travel information"
    return (p + suffix)[:450]
