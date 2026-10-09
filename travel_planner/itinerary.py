"""Small deterministic helpers for rendering/editing day-wise itinerary sections."""
from __future__ import annotations
import re

DAY_HEADING = re.compile(r"(?im)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?(?:day\s+\d+|day\s+one|day\s+two|day\s+three|day\s+four|day\s+five|day\s+six|day\s+seven)(?:\s*[:—–-].*)?(?:\*\*)?\s*$")

def extract_day_sections(markdown: str) -> list[dict[str, str]]:
    lines = (markdown or "").splitlines()
    found = []
    for i, line in enumerate(lines):
        if DAY_HEADING.match(line.strip()):
            found.append((i, line.strip().replace("**", "").lstrip("# ").strip()))
    sections = []
    for idx, (start, heading) in enumerate(found):
        end = found[idx + 1][0] if idx + 1 < len(found) else len(lines)
        body = "\n".join(lines[start + 1:end]).strip()
        sections.append({"heading": heading, "body": body})
    return sections

def parse_budget_table(markdown: str) -> list[dict[str, str]]:
    """Return simple markdown table rows whose first cell looks like a cost category."""
    rows = []
    for line in (markdown or "").splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or all(re.fullmatch(r"[-: ]+", c or " ") for c in cells):
            continue
        if cells[0].lower() in {"category", "item", "expense", "cost", "budget item"}:
            continue
        if re.search(r"\b(transport|accommodation|hotel|food|meal|activity|tickets?|local travel|contingency|total|estimate)\b", cells[0], re.I):
            rows.append({"category": cells[0], "amount": cells[1], "details": " | ".join(cells[2:])})
    return rows
