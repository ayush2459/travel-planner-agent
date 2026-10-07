from __future__ import annotations
import json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATASET=ROOT/"eval_dataset.json"; RESULTS=ROOT/"evaluation_results.json"
PROMPT="""You are an impartial evaluator for a Travel Planner Agent. Score the actual response against expected behavior on Correctness, Relevance, Completeness and Tool Usage, each 0-1. Return JSON only with keys correctness,relevance,completeness,tool_usage,reason."""
def run():
    from google import genai
    key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key: raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY; never commit it.")
    client=genai.Client(api_key=key)
    ds=json.loads(DATASET.read_text(encoding="utf-8")); results=json.loads(RESULTS.read_text(encoding="utf-8"))
    by={r["test_case"]:r for r in results["results"]}
    for case in ds["test_cases"]:
        row=by[case["id"]]
        if not row["actual_response"]: continue
        prompt=PROMPT+"\nTest Case:\n"+json.dumps(case,ensure_ascii=False)+"\nActual Response:\n"+row["actual_response"]+"\nMetadata:\n"+json.dumps(row["metadata"])
        text=client.models.generate_content(model="gemini-2.5-flash",contents=prompt).text.strip().replace("```json","").replace("```","").strip()
        j=json.loads(text); j["overall"]=round(sum(float(j[k]) for k in ["correctness","relevance","completeness","tool_usage"])/4,3); row["gemini_judge"]=j
    vals=[r["gemini_judge"]["overall"] for r in results["results"] if "gemini_judge" in r]
    results["evaluation_type"]="Gemini LLM-as-a-Judge"; results["gemini_overall_score"]=round(sum(vals)/len(vals),3) if vals else None
    results["gemini_overall_percentage"]=f"{results['gemini_overall_score']*100:.1f}%" if vals else None
    RESULTS.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"gemini_overall_percentage":results["gemini_overall_percentage"]},indent=2))
if __name__=="__main__": run()
