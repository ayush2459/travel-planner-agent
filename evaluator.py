from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "eval_dataset.json"
RESULTS = ROOT / "evaluation_results.json"

sys.path.insert(0, str(ROOT))


def load_dataset():
    """Load the evaluation dataset regardless of its top-level JSON structure."""

    if not DATASET.exists():
        raise FileNotFoundError(
            f"Evaluation dataset not found: {DATASET}"
        )

    data = json.loads(
        DATASET.read_text(encoding="utf-8")
    )

    # Expected format:
    # [
    #   {"id": "...", "prompt": "...", ...}
    # ]
    if isinstance(data, list):
        dataset = data

    # Handle object-wrapped datasets.
    elif isinstance(data, dict):
        dataset = None

        for key in (
            "test_cases",
            "cases",
            "evaluation_cases",
            "tests",
            "dataset",
        ):
            value = data.get(key)

            if isinstance(value, list):
                dataset = value
                break

        # Fallback: find the first list containing dictionaries.
        if dataset is None:
            for value in data.values():
                if (
                    isinstance(value, list)
                    and value
                    and all(isinstance(item, dict) for item in value)
                ):
                    dataset = value
                    break

        if dataset is None:
            raise ValueError(
                "Could not find a list of test cases in eval_dataset.json."
            )

    else:
        raise ValueError(
            "eval_dataset.json must contain either a list or an object."
        )

    # Validate individual test cases.
    valid_cases = []

    for index, case in enumerate(dataset, start=1):
        if not isinstance(case, dict):
            print(
                f"Warning: skipping invalid test case #{index}: "
                f"{type(case).__name__}"
            )
            continue

        # Make sure every case has an ID and prompt.
        case = dict(case)

        if not case.get("id"):
            case["id"] = f"TC{index:02d}"

        if "prompt" not in case:
            case["prompt"] = ""

        valid_cases.append(case)

    if not valid_cases:
        raise ValueError(
            "No valid test cases were found in eval_dataset.json."
        )

    return valid_cases


def score_case(case, output):
    """
    Fast transparent baseline evaluator.

    Scores:
      - correctness
      - relevance
      - completeness
      - tool_usage
    """

    text = (output or "").strip().lower()

    if not text:
        return {
            "correctness": 0.0,
            "relevance": 0.0,
            "completeness": 0.0,
            "tool_usage": 0.0,
            "overall": 0.0,
            "reason": "Empty agent response",
        }

    expected = case.get("expected", {})
    if not isinstance(expected, dict):
        expected = {}

    test_type = str(
        case.get("type", "normal")
    ).lower()

    correctness = 1.0
    relevance = 1.0
    completeness = 1.0
    tool_usage = 1.0

    required_terms = expected.get(
        "required_terms",
        [],
    )

    if not isinstance(required_terms, list):
        required_terms = []

    required_terms = [
        str(term).lower()
        for term in required_terms
        if term
    ]

    # ---------------------------------------------------------
    # Validation / missing-input cases
    # ---------------------------------------------------------
    if test_type == "validation":

        if required_terms:
            found = sum(
                1
                for term in required_terms
                if term in text
            )

            correctness = found / len(required_terms)

        completeness = correctness

    # ---------------------------------------------------------
    # Current / live-information cases
    # ---------------------------------------------------------
    elif test_type == "tool_required":

        if required_terms:
            found = sum(
                1
                for term in required_terms
                if term in text
            )

            correctness = found / len(required_terms)

        source_words = [
            "source",
            "sources",
            "official",
            "website",
            "according to",
            "verified",
            "reference",
            "references",
        ]

        if any(
            word in text
            for word in source_words
        ):
            tool_usage = 1.0
        else:
            tool_usage = 0.5

    # ---------------------------------------------------------
    # Normal travel-planning cases
    # ---------------------------------------------------------
    else:

        if required_terms:
            found = sum(
                1
                for term in required_terms
                if term in text
            )

            correctness = found / len(required_terms)

        structure_terms = [
            "itinerary",
            "budget",
            "day",
            "trip",
        ]

        structure_hits = sum(
            1
            for term in structure_terms
            if term in text
        )

        completeness = min(
            1.0,
            structure_hits / 3,
        )

    overall = (
        correctness
        + relevance
        + completeness
        + tool_usage
    ) / 4

    return {
        "correctness": round(correctness, 3),
        "relevance": round(relevance, 3),
        "completeness": round(completeness, 3),
        "tool_usage": round(tool_usage, 3),
        "overall": round(overall, 3),
    }


def save_results(results):
    """Save results after every test case."""

    if results:
        overall = (
            sum(
                item["scores"]["overall"]
                for item in results
            )
            / len(results)
        )
    else:
        overall = 0.0

    failed = [
        item["id"]
        for item in results
        if item["scores"]["overall"] < 0.75
    ]

    payload = {
        "evaluation_type": (
            "Assignment 2 - Agent Evaluation"
        ),
        "completed_cases": len(results),
        "overall_score": round(overall, 3),
        "overall_percentage": round(
            overall * 100,
            2,
        ),
        "failed_test_cases": failed,
        "results": results,
        "note": (
            "Results are saved incrementally "
            "after every test case."
        ),
    }

    RESULTS.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main():

    if "--run" not in sys.argv:
        print()
        print("Usage:")
        print(
            '  ".\\.venv\\Scripts\\python.exe" '
            "evaluator.py --run"
        )
        print()
        return

    print()
    print("=" * 65)
    print(
        "TRAVEL PLANNER AGENT - "
        "ASSIGNMENT 2 EVALUATION"
    )
    print("=" * 65)

    try:
        dataset = load_dataset()
    except Exception as exc:
        print()
        print("ERROR LOADING DATASET")
        print("-" * 65)
        print(str(exc))
        print()
        return

    print(
        f"Test cases: {len(dataset)}"
    )

    # Import only after the dataset has been validated.
    try:
        from travel_planner.agent import ask_agent
    except Exception as exc:
        print()
        print("ERROR IMPORTING TRAVEL AGENT")
        print("-" * 65)
        print(str(exc))
        print()
        return

    print("Model: local Ollama")
    print("=" * 65)
    print()

    results = []
    total = len(dataset)

    for index, case in enumerate(
        dataset,
        start=1,
    ):

        case_id = case.get(
            "id",
            f"TC{index:02d}",
        )

        prompt = str(
            case.get(
                "prompt",
                "",
            )
        )

        print(
            f"[{index}/{total}] "
            f"{case_id} - running...",
            flush=True,
        )

        start = time.time()

        try:

            response = ask_agent(prompt)

            elapsed = time.time() - start

            # Some versions of the agent may return:
            # (answer, metadata)
            if isinstance(response, tuple):
                output = response[0]
            else:
                output = response

            if output is None:
                output = ""

            output = str(output)

            scores = score_case(
                case,
                output,
            )

            result = {
                "id": case_id,
                "prompt": prompt,
                "elapsed_seconds": round(
                    elapsed,
                    2,
                ),
                "scores": scores,
                "response": output,
            }

            results.append(result)

            # IMPORTANT:
            # Save immediately after every case.
            save_results(results)

            print(
                f"    completed in "
                f"{elapsed:.1f}s "
                f"| score="
                f"{scores['overall']:.2f}",
                flush=True,
            )

        except KeyboardInterrupt:

            print()
            print(
                "Evaluation interrupted by user."
            )

            print(
                f"Completed cases: "
                f"{len(results)}/{total}"
            )

            print(
                "Saving completed results..."
            )

            save_results(results)

            print(
                f"Results saved to: {RESULTS}"
            )

            print()
            return

        except Exception as exc:

            elapsed = time.time() - start

            result = {
                "id": case_id,
                "prompt": prompt,
                "elapsed_seconds": round(
                    elapsed,
                    2,
                ),
                "scores": {
                    "correctness": 0.0,
                    "relevance": 0.0,
                    "completeness": 0.0,
                    "tool_usage": 0.0,
                    "overall": 0.0,
                },
                "error": str(exc),
            }

            results.append(result)

            # Save even failed cases.
            save_results(results)

            print(
                f"    FAILED in "
                f"{elapsed:.1f}s: "
                f"{exc}",
                flush=True,
            )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    if not results:
        print()
        print("No test cases completed.")
        return

    overall = (
        sum(
            item["scores"]["overall"]
            for item in results
        )
        / len(results)
    )

    failed = [
        item["id"]
        for item in results
        if item["scores"]["overall"] < 0.75
    ]

    print()
    print("=" * 65)
    print("EVALUATION COMPLETE")
    print("=" * 65)

    print(
        f"Completed: "
        f"{len(results)}/{total}"
    )

    print(
        f"Overall score: "
        f"{overall:.3f}"
    )

    print(
        f"Overall percentage: "
        f"{overall * 100:.2f}%"
    )

    print(
        "Failed cases: "
        + (
            ", ".join(failed)
            if failed
            else "None"
        )
    )

    print("=" * 65)
    print()

    print(
        f"Detailed results: {RESULTS}"
    )


if __name__ == "__main__":
    main()