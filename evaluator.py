from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "eval_dataset.json"
RESULTS = ROOT / "evaluation_results.json"

sys.path.insert(0, str(ROOT))


# ------------------------------------------------------------
# DATASET LOADING
# ------------------------------------------------------------

def load_dataset():
    if not DATASET.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET}"
        )

    data = json.loads(
        DATASET.read_text(encoding="utf-8")
    )

    # Direct list
    if isinstance(data, list):
        cases = data

    # Wrapped list
    elif isinstance(data, dict):
        cases = None

        for key in (
            "test_cases",
            "cases",
            "evaluation_cases",
            "tests",
            "dataset",
            "items",
        ):
            value = data.get(key)

            if isinstance(value, list):
                cases = value
                break

        # Fallback: find a list of dictionaries
        if cases is None:
            for value in data.values():
                if (
                    isinstance(value, list)
                    and value
                    and all(
                        isinstance(x, dict)
                        for x in value
                    )
                ):
                    cases = value
                    break

        if cases is None:
            raise ValueError(
                "Could not find test cases in eval_dataset.json."
            )

    else:
        raise ValueError(
            "eval_dataset.json must contain a JSON "
            "list or object."
        )

    if not cases:
        raise ValueError(
            "The evaluation dataset contains no test cases."
        )

    return cases


# ------------------------------------------------------------
# PROMPT EXTRACTION
# ------------------------------------------------------------

PROMPT_FIELDS = (
    "prompt",
    "input",
    "query",
    "question",
    "user_input",
    "user_prompt",
    "request",
    "message",
    "task",
    "instruction",
)


def extract_prompt(case):
    """
    Find the actual user request regardless of which
    common field name the dataset uses.
    """

    for field in PROMPT_FIELDS:
        value = case.get(field)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # Sometimes the prompt is nested.
    for parent in (
        "input_data",
        "user",
        "request_data",
        "test",
    ):
        nested = case.get(parent)

        if isinstance(nested, dict):
            for field in PROMPT_FIELDS:
                value = nested.get(field)

                if (
                    isinstance(value, str)
                    and value.strip()
                ):
                    return value.strip()

    return ""


def normalize_cases(raw_cases):
    cases = []

    for index, raw_case in enumerate(
        raw_cases,
        start=1,
    ):

        if not isinstance(raw_case, dict):
            raise ValueError(
                f"Test case #{index} is not an object."
            )

        case = dict(raw_case)

        case_id = (
            case.get("id")
            or case.get("test_id")
            or f"TC{index:02d}"
        )

        prompt = extract_prompt(case)

        if not prompt:
            available_keys = ", ".join(
                str(k)
                for k in case.keys()
            )

            raise ValueError(
                f"{case_id} has no usable prompt. "
                f"Available fields: {available_keys}"
            )

        case["_id"] = str(case_id)
        case["_prompt"] = prompt

        cases.append(case)

    return cases


# ------------------------------------------------------------
# SCORING
# ------------------------------------------------------------

def get_expected_terms(case):
    expected = case.get("expected", {})

    if not isinstance(expected, dict):
        expected = {}

    terms = expected.get(
        "required_terms",
        [],
    )

    if not isinstance(terms, list):
        terms = []

    return [
        str(term).lower().strip()
        for term in terms
        if str(term).strip()
    ]


def score_case(case, output):
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

    test_type = str(
        case.get("type", "normal")
    ).lower()

    expected_terms = get_expected_terms(case)

    # --------------------------------------------------------
    # Correctness
    # --------------------------------------------------------

    if expected_terms:
        found = sum(
            1
            for term in expected_terms
            if term in text
        )

        correctness = found / len(
            expected_terms
        )
    else:
        correctness = 1.0

    # --------------------------------------------------------
    # Relevance
    # --------------------------------------------------------

    # The response should actually discuss the requested
    # subject instead of merely asking for information.

    prompt = case["_prompt"].lower()

    destination_words = [
        "jaipur",
        "delhi",
        "rishikesh",
        "india",
        "japan",
        "france",
        "paris",
    ]

    mentioned_destination = any(
        word in prompt
        for word in destination_words
    )

    if mentioned_destination:
        relevance = 1.0

        # If a specific destination was requested but
        # response ignores it completely, reduce relevance.
        destination_hits = [
            word
            for word in destination_words
            if word in prompt and word in text
        ]

        if not destination_hits:
            relevance = 0.0
    else:
        relevance = 1.0

    # --------------------------------------------------------
    # Completeness
    # --------------------------------------------------------

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

    if test_type in (
        "validation",
        "invalid",
        "missing",
    ):
        completeness = 1.0

    elif structure_hits:
        completeness = min(
            1.0,
            structure_hits / 3,
        )

    else:
        completeness = 0.0

    # --------------------------------------------------------
    # Tool usage
    # --------------------------------------------------------

    if test_type in (
        "tool_required",
        "live",
        "current",
    ):

        source_words = [
            "source",
            "sources",
            "official",
            "website",
            "reference",
            "references",
            "verified",
            "according to",
        ]

        tool_usage = (
            1.0
            if any(
                word in text
                for word in source_words
            )
            else 0.0
        )

    else:
        tool_usage = 1.0

    overall = (
        correctness
        + relevance
        + completeness
        + tool_usage
    ) / 4

    return {
        "correctness": round(
            correctness,
            3,
        ),
        "relevance": round(
            relevance,
            3,
        ),
        "completeness": round(
            completeness,
            3,
        ),
        "tool_usage": round(
            tool_usage,
            3,
        ),
        "overall": round(
            overall,
            3,
        ),
    }


# ------------------------------------------------------------
# RESULT SAVING
# ------------------------------------------------------------

def save_results(results, total):
    if results:
        overall = sum(
            item["scores"]["overall"]
            for item in results
        ) / len(results)
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
        "total_cases": total,
        "overall_score": round(
            overall,
            3,
        ),
        "overall_percentage": round(
            overall * 100,
            2,
        ),
        "failed_test_cases": failed,
        "results": results,
        "note": (
            "Results are saved after every "
            "completed test case."
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


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    if "--run" not in sys.argv:
        print(
            'Usage: ".\\.venv\\Scripts\\python.exe" '
            "evaluator.py --run"
        )
        return

    print()
    print("=" * 70)
    print(
        "TRAVEL PLANNER AGENT - "
        "ASSIGNMENT 2 EVALUATION"
    )
    print("=" * 70)

    # Load dataset
    try:
        raw_cases = load_dataset()
        cases = normalize_cases(raw_cases)

    except Exception as exc:
        print()
        print("DATASET ERROR")
        print("-" * 70)
        print(exc)
        print()
        print(
            "The evaluator has NOT started the model."
        )
        return

    total = len(cases)

    print(
        f"Test cases: {total}"
    )
    print(
        "Model: local Ollama"
    )
    print("=" * 70)
    print()

    # Import agent
    try:
        from travel_planner.agent import ask_agent

    except Exception as exc:
        print()
        print("AGENT IMPORT ERROR")
        print("-" * 70)
        print(exc)
        return

    results = []

    # --------------------------------------------------------
    # Run cases
    # --------------------------------------------------------

    for index, case in enumerate(
        cases,
        start=1,
    ):

        case_id = case["_id"]
        prompt = case["_prompt"]

        print(
            f"[{index}/{total}] "
            f"{case_id} - running...",
            flush=True,
        )

        # Show the actual prompt so we can verify that
        # the evaluator is not sending an empty string.
        print(
            f"    Prompt: {prompt}",
            flush=True,
        )

        start = time.time()

        try:

            response = ask_agent(prompt)

            elapsed = (
                time.time() - start
            )

            if isinstance(
                response,
                tuple,
            ):
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

            save_results(
                results,
                total,
            )

            print(
                f"    Completed in "
                f"{elapsed:.1f}s "
                f"| score="
                f"{scores['overall']:.2f}",
                flush=True,
            )

        except KeyboardInterrupt:

            print()
            print(
                "Evaluation interrupted."
            )

            save_results(
                results,
                total,
            )

            print(
                f"Saved {len(results)}/"
                f"{total} completed cases."
            )

            return

        except Exception as exc:

            elapsed = (
                time.time() - start
            )

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

            save_results(
                results,
                total,
            )

            print(
                f"    FAILED in "
                f"{elapsed:.1f}s: "
                f"{exc}",
                flush=True,
            )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    if not results:
        print(
            "No cases completed."
        )
        return

    overall = sum(
        item["scores"]["overall"]
        for item in results
    ) / len(results)

    failed = [
        item["id"]
        for item in results
        if item["scores"]["overall"] < 0.75
    ]

    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)

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

    print("=" * 70)
    print()

    print(
        f"Detailed results: {RESULTS}"
    )


if __name__ == "__main__":
    main()