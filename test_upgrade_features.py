from __future__ import annotations
import os, tempfile
from travel_planner.budget import calculate_budget, compare_budget
from travel_planner.itinerary import extract_day_sections, parse_budget_table
from travel_planner.trip_store import save_trip, list_trips, load_trip, list_revisions, load_revision, delete_trip
from pdf_report import build_itinerary_pdf, budget_data_from_meta
from travel_planner.travel_tools import format_weather_summary


def test_budget():
    result = calculate_budget({"Transport": 2000, "Accommodation": 4000, "Food": 1500, "Activities": 800, "Local travel": 500, "Contingency": 700})
    assert result["total"] == 9500
    assert compare_budget(result["total"], 10000)["within_budget"] is True
    assert compare_budget(result["total"], 9000)["within_budget"] is False


def test_itinerary():
    text = "## Summary\nTrip\n\n### Day 1 — Forts\nVisit fort\n\n### Day 2 — Food\nTry local food\n\n| Category | Amount | Notes |\n|---|---:|---|\n| Transport | ₹2,000 | train |\n| Food | ₹1,000 | meals |"
    days = extract_day_sections(text)
    assert len(days) == 2 and "Visit fort" in days[0]["body"]
    costs = parse_budget_table(text)
    assert len(costs) == 2 and costs[0]["category"] == "Transport"


def test_trip_store_roundtrip():
    owner = "test-owner-" + os.urandom(5).hex()
    trip = os.urandom(16).hex()
    messages = [{"role": "user", "content": "Plan a trip to Jaipur"}, {"role": "assistant", "content": "## Day 1 — Jaipur\nVisit a fort", "meta": {"provider": "test"}}]
    save_trip(owner, trip, messages)
    rows = list_trips(owner)
    assert any(r["id"] == trip for r in rows)
    loaded = load_trip(owner, trip)
    assert loaded and loaded[0]["content"] == messages[0]["content"]
    assert load_trip("different-owner", trip) is None
    revisions = list_revisions(owner, trip)
    assert revisions
    restored = load_revision(owner, trip, revisions[0]["id"])
    assert restored and len(restored) == 2
    assert delete_trip(owner, trip) is True
    assert load_trip(owner, trip) is None


def test_pdf_includes_weather_and_calculator_data():
    meta = {
        "city": "Jaipur",
        "budget_calculator": {
            "categories": {"Transport": 2000, "Accommodation": 4000, "Food": 1500},
            "total": 7500, "limit": 10000, "currency": "INR",
        },
        "weather": {
            "place": "Jaipur, Rajasthan, India", "temperature_2m": 31,
            "apparent_temperature": 33, "precipitation": 0, "weather_code": 1,
            "weather_description": "Mainly clear", "relative_humidity_2m": 40,
            "wind_speed_10m": 9, "time": "2026-10-09T15:00", "timezone": "Asia/Kolkata",
        },
    }
    chart = budget_data_from_meta(meta)
    assert chart and chart["budget"] == 10000 and chart["currency"] == "INR"
    md = "# Jaipur Trip\n\n## Summary\nA three-day trip.\n\n## Day 1 — Heritage\nVisit a fort and explore the old city.\n"
    payload = build_itinerary_pdf(md, meta)
    assert payload.startswith(b"%PDF") and len(payload) > 5000


def test_weather_summary_includes_temperature():
    summary = format_weather_summary({
        "place": "Jaipur, Rajasthan, India",
        "temperature_2m": 31,
        "apparent_temperature": 33,
        "relative_humidity_2m": 40,
        "wind_speed_10m": 9,
        "precipitation": 0,
        "weather_description": "Mainly clear",
        "time": "2026-10-09T15:00",
        "timezone": "Asia/Kolkata",
    })
    assert "Temperature: 31°C" in summary
    assert "feels like: 33°C" in summary
    assert "2026-10-09T15:00" in summary
    assert "not a forecast" in summary


if __name__ == "__main__":
    test_budget()
    test_itinerary()
    test_trip_store_roundtrip()
    test_pdf_includes_weather_and_calculator_data()
    test_weather_summary_includes_temperature()
    print("Upgrade feature tests: PASS")
