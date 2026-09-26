"""
Contract Risk Explainer - Mini Evaluation Benchmark
Evaluates the model's accuracy on the 15 hand-labeled test clauses in eval_set.json.
Run standalone with: python eval.py
"""

import os
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI
from app import clean_json_string, call_model_api, STAGE2_SYSTEM_PROMPT, NEBIUS_BASE_URL, DEFAULT_MODEL

load_dotenv()

logging.basicConfig(level=logging.WARNING)

def run_evaluation():
    eval_file = os.path.join(os.path.dirname(__file__), "eval_set.json")
    if not os.path.exists(eval_file):
        print(f"Error: Could not find {eval_file}")
        return

    with open(eval_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    api_key = os.getenv("NEBIUS_API_KEY", "").strip()
    if not api_key:
        print("Error: NEBIUS_API_KEY is not set in .env. Please configure your key first.")
        return

    client = OpenAI(
        base_url=NEBIUS_BASE_URL,
        api_key=api_key
    )

    model_name = os.getenv("NEBIUS_MODEL", DEFAULT_MODEL)
    print("=" * 70)
    print(f"  CONTRACT RISK EXPLAINER - BENCHMARK EVALUATION")
    print(f"  Target Model : {model_name}")
    print(f"  Dataset Size : {len(test_cases)} hand-labeled test clauses")
    print("=" * 70)

    # Format all clauses for deep analysis
    payload = []
    for tc in test_cases:
        payload.append({
            "id": tc["id"],
            "text": tc["text"],
            "preliminary_risk": "unspecified"
        })

    user_prompt = f"Analyze these contract clauses and return risk_level, confidence, explanation, and suggested_revision:\n\n{json.dumps(payload, indent=2)}"

    print("\nSending batch evaluation request to Nebius Token Factory...")
    raw_response = call_model_api(client, STAGE2_SYSTEM_PROMPT, user_prompt)
    cleaned = clean_json_string(raw_response)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as err:
        print(f"Failed to parse JSON response: {err}")
        print(f"Raw response:\n{raw_response}")
        return

    returned_clauses = data.get("clauses", []) if isinstance(data, dict) else []
    results_map = {}
    for rc in returned_clauses:
        if isinstance(rc, dict) and "id" in rc:
            results_map[rc["id"]] = rc

    correct_count = 0
    misclassified = []

    print("\n" + "-" * 70)
    print(f"{'ID':<4} {'Category':<22} {'Expected':<10} {'Predicted':<10} {'Status'}")
    print("-" * 70)

    for tc in test_cases:
        tc_id = tc["id"]
        expected = tc["expected_risk_level"].lower()
        pred_item = results_map.get(tc_id, {})
        predicted = str(pred_item.get("risk_level", "unknown")).lower()
        confidence = pred_item.get("confidence", "high")

        is_match = (expected == predicted)
        if is_match:
            correct_count += 1
            status = "✅ PASS"
        else:
            status = "❌ MISMATCH"
            misclassified.append({
                "id": tc_id,
                "text": tc["text"],
                "expected": expected,
                "predicted": predicted,
                "category": tc.get("category", ""),
                "explanation": pred_item.get("explanation", "N/A")
            })

        print(f"{tc_id:<4} {tc.get('category', ''):<22} {expected:<10} {predicted:<10} {status}")

    total = len(test_cases)
    accuracy = (correct_count / total) * 100 if total > 0 else 0

    print("=" * 70)
    print(f"  BENCHMARK SUMMARY")
    print(f"  Total Tested : {total}")
    print(f"  Correct      : {correct_count}")
    print(f"  Accuracy     : {accuracy:.1f}%")
    print("=" * 70)

    if misclassified:
        print("\n🔍 Misclassified Clauses Breakdown:")
        for m in misclassified:
            print(f"\n  [Clause #{m['id']} - {m['category']}]")
            print(f"  Text     : \"{m['text']}\"")
            print(f"  Expected : {m['expected'].upper()}")
            print(f"  Predicted: {m['predicted'].upper()}")
            print(f"  Reason   : {m['explanation']}")
    else:
        print("\n🎉 Perfect match! All clauses correctly classified according to the benchmark.")

if __name__ == "__main__":
    run_evaluation()
