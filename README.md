# Personal Travel Planner Agent (Google ADK)

An AI agent built with [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) that turns a free-text travel request into a budget-aware, day-wise itinerary for trips in India and abroad.

**Example input**
> I want to visit Jaipur for 3 days with a budget of ₹15,000. I like history and local food.

## What it does

1. **Understands the request**: destination, days, budget, travellers, interests (asks one question if something essential is missing).
2. **Recommends places** ranked by the user's interests (tool: `get_destination_info`).
3. **Estimates the budget** with an itemised breakdown and checks it against the user's budget (tool: `estimate_budget`).
4. **Suggests a day-wise plan** (morning / afternoon / evening + where to eat) with tips.

## Project structure

```
travel_planner_agent/
├── travel_planner/
│   ├── __init__.py
│   └── agent.py          # agent, tools and instructions
├── requirements.txt
├── .env.example
├── example_conversations.md
└── README.md
```

ADK expects the agent folder to expose a `root_agent`; `agent.py` defines it and `__init__.py` imports it.

## How it works

| Part | Description |
|------|-------------|
| `root_agent` | An ADK `Agent` using `gemini-2.5-flash` with a structured instruction (workflow + fixed output format). |
| `get_destination_info(city, interests)` | Function tool over a small built-in dataset (Jaipur, Udaipur, Goa, Paris). Ranks places and food by interest tags and returns tips (closing days, tickets). For other cities it tells the model to use general knowledge and flag estimates. |
| `estimate_budget(city, days, budget_inr, travelers, entry_fees_per_person)` | Function tool that computes stay, food, local transport, entry fees and misc using budget / mid / comfort rates, picks the best tier that leaves a reserve for flights and other costs (20% for India, 40% for international trips), and returns a verdict (`comfortable`, `tight`, `over_budget`). If no budget is given it returns all three tiers. A per-city cost multiplier scales the rates (Paris is 4x an average Indian city). |

The model is told to use only the tool's numbers for the budget, so totals are deterministic rather than hallucinated.

## Setup

Requires Python 3.10+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Gemini API key (free key: https://aistudio.google.com/apikey)
cp .env.example travel_planner/.env
# then edit travel_planner/.env and paste your key
```

## Run

Run these from the project root (the folder that contains `travel_planner/`).

```bash
adk web                      # opens a chat UI at http://localhost:8000
# or
adk run travel_planner       # chat in the terminal
```

In `adk web`, pick **travel_planner** from the dropdown and try the example input above.

## Example prompts

- `I want to visit Jaipur for 3 days with a budget of ₹15,000. I like history and local food.`
- `Plan 2 days in Udaipur for 2 people, budget ₹8,000. We love sunsets and photography.`
- `4 days in Goa for 2 people with ₹20,000, we want beaches and some history.`
- `Plan a 7 day trip to Paris for me. I like art, history and food.` (no budget given, so it shows budget / mid / comfort options)

See `example_conversations.md` for sample conversations.

## Notes and limitations

- Prices and entry fees are approximate planning figures, not live data. Verify before booking.
- Intercity travel and, for international trips, return flights, visa and insurance are not included in the estimate; the "remaining" amount is meant to cover them.
- Built-in data covers Jaipur, Udaipur, Goa and Paris. Other cities, in India or abroad, work through the model's general knowledge (the model supplies a cost multiplier), and the agent states that figures are rough.
- International fees are converted to INR at an approximate rate; check current prices and your passport's visa rules before booking.
- The model name can be changed without editing code by setting the `TRAVEL_AGENT_MODEL` environment variable.

## Ideas for extension

- Add a `google_search` tool or a Maps/Places API for live data.
- Add a weather tool and adjust the itinerary for rain or heat.
- Add session state to remember preferences across turns.

## Smart Conversation Memory

The current version is conversation-aware. Follow-up requests such as `make it cheaper`, `change day 2`, `I am vegetarian`, or `what is the total now?` use the relevant previous messages from the current Streamlit session. See `SMART_MEMORY.md` for details and testing.

## Smart Travel Suite v2 additions

See [`SMART_UPGRADE_GUIDE.md`](SMART_UPGRADE_GUIDE.md) for local setup, tests, deployment notes, and limitations. This build adds saved trips with revision snapshots, day-by-day itinerary tabs, a deterministic budget calculator, current weather lookup, currency conversion, and optional PostgreSQL persistence while retaining Ollama/Groq, fact-check search, and PDF reports.

**Privacy note:** saved trips are scoped to a random workspace token in the URL. Treat that URL as private. This is not a multi-user authenticated service; do not use it for sensitive personal data or expose it to multiple users until authentication and per-user authorization are implemented.
