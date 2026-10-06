# Live Fact-Check Guard

This Ollama build includes a real web-search guard independent of Gemini.

- Uses the `ddgs` Python package to retrieve live search results.
- Sends search evidence to the local Ollama model.
- Instructs the model to prefer official government, embassy, tourism-board,
  attraction, and transport-operator sources for time-sensitive claims.
- Shows the sources used in an expandable UI section.
- If search fails, the UI warns that current facts should be verified manually.
- No Gemini API key is required for generation.

The search layer is not a guarantee that every result is official; the model is
explicitly instructed to distinguish official sources and uncertainty.
