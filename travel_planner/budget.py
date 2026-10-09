"""Deterministic budget helpers independent of model-generated arithmetic."""
from __future__ import annotations
CATEGORIES = ("Transport", "Accommodation", "Food", "Activities", "Local travel", "Contingency")

def calculate_budget(values: dict[str, float]) -> dict:
    cleaned = {}
    for category in CATEGORIES:
        try:
            value = float(values.get(category, 0) or 0)
        except (TypeError, ValueError):
            raise ValueError(f"{category} must be a number.")
        if value < 0:
            raise ValueError(f"{category} cannot be negative.")
        cleaned[category] = round(value, 2)
    total = round(sum(cleaned.values()), 2)
    return {"categories": cleaned, "total": total, "largest_category": max(cleaned, key=cleaned.get) if total else None}

def compare_budget(estimate: float, limit: float) -> dict:
    estimate, limit = float(estimate), float(limit)
    return {"estimate": estimate, "limit": limit, "difference": round(limit - estimate, 2), "within_budget": estimate <= limit}
