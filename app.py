import os
import json
import re
import logging
# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, render_template
# pyrefly: ignore [missing-import]
from openai import OpenAI
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
STAGE1_SYSTEM_PROMPT = (
    "You are a fast contract triage analyst. Split the input contract into individual clauses or provisions. "
    "For each clause, assign a quick preliminary risk_level ('high', 'medium', or 'low'). Do not include explanations.\n\n"
    "Respond with ONLY a raw JSON object starting with { and ending with }:\n"
    "{\n"
    '  "clauses": [\n'
    '    {"text": "...", "risk_level": "high|medium|low"}\n'
    '  ]\n'
    "}"
)

STAGE2_SYSTEM_PROMPT = (
    "You are an expert contract-risk analyst. For each provided clause, conduct a deep legal analysis. "
    "Return a finalized risk_level ('high', 'medium', or 'low') and a concise, one-sentence plain-English explanation "
    "of why this clause carries that risk to the user/consumer.\n\n"
    "Respond with ONLY a raw JSON object starting with { and ending with }:\n"
    "{\n"
    '  "clauses": [\n'
    '    {"id": 0, "risk_level": "high|medium|low", "explanation": "..."}\n'
    '  ]\n'
    "}"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_openai_client():
    api_key = os.getenv("NEBIUS_API_KEY", "").strip()
    return OpenAI(
        base_url=NEBIUS_BASE_URL,
        api_key=api_key if api_key else "dummy_key_placeholder"
    )

def clean_json_string(raw: str) -> str:
    """Removes markdown code fences and extracts substring from first '{' to last '}'."""
    if not raw:
        return ""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        cleaned = cleaned[start_idx:end_idx + 1]

    return cleaned.strip()

def call_model_api(client: OpenAI, system_prompt: str, user_prompt: str) -> str:
    """Sends a completion request to Nebius Token Factory with JSON mode & fallback."""
    model_name = os.getenv("NEBIUS_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    params = {
        "model": model_name,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"}
    }

    try:
        response = client.chat.completions.create(**params)
    except Exception as e:
        err_str = str(e).lower()
        if "response_format" in err_str or "json_object" in err_str or "unsupported" in err_str or "not supported" in err_str:
            logger.info("response_format parameter not supported by model; falling back without response_format.")
            params.pop("response_format", None)
            response = client.chat.completions.create(**params)
        else:
            raise

    return response.choices[0].message.content

# ---------------------------------------------------------------------------
# Stage 1 - Fast Scan
# ---------------------------------------------------------------------------
def scan_clauses(client: OpenAI, contract_text: str) -> list[dict]:
    """Stage 1: Fast triage to split contract into clauses with preliminary risk levels."""
    raw_response = None
    try:
        logger.info("Executing Stage 1: Fast Scan...")
        raw_response = call_model_api(
            client,
            STAGE1_SYSTEM_PROMPT,
            f"Triage this contract text into clauses and preliminary risk levels:\n\n{contract_text}"
        )
        print(f"\n--- [Stage 1 Raw Model Response] ---\n{raw_response}\n------------------------------------\n")
        cleaned = clean_json_string(raw_response)
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as first_err:
        logger.warning(f"Stage 1 JSON parsing failed: {first_err}. Retrying with stricter prompt...")
        retry_sys_prompt = STAGE1_SYSTEM_PROMPT + "\n\nCRITICAL RETRY: Output strictly raw JSON starting with { and ending with }."
        raw_response = call_model_api(
            client,
            retry_sys_prompt,
            f"Triage this contract text into clauses and preliminary risk levels:\n\n{contract_text}"
        )
        print(f"\n--- [Stage 1 Retry Raw Model Response] ---\n{raw_response}\n------------------------------------------\n")
        cleaned = clean_json_string(raw_response)
        data = json.loads(cleaned)

    clauses = data.get("clauses", []) if isinstance(data, dict) else []
    normalized = []
    for item in clauses:
        if isinstance(item, dict) and item.get("text"):
            r_level = str(item.get("risk_level", "low")).lower().strip()
            if r_level not in ["high", "medium", "low"]:
                r_level = "medium"
            normalized.append({
                "text": item.get("text", "").strip(),
                "risk_level": r_level
            })
    return normalized

# ---------------------------------------------------------------------------
# Stage 2 - Deep Analysis
# ---------------------------------------------------------------------------
def deep_analyze(client: OpenAI, flagged_clauses: list[dict]) -> dict[int, dict]:
    """Stage 2: Detailed analysis for flagged high/medium clauses."""
    if not flagged_clauses:
        return {}

    user_payload = []
    for c in flagged_clauses:
        user_payload.append({
            "id": c["id"],
            "text": c["text"],
            "preliminary_risk": c["risk_level"]
        })

    user_prompt = f"Analyze these flagged contract clauses in detail:\n\n{json.dumps(user_payload, indent=2)}"

    raw_response = None
    try:
        logger.info(f"Executing Stage 2: Deep Analysis on {len(flagged_clauses)} flagged clauses...")
        raw_response = call_model_api(client, STAGE2_SYSTEM_PROMPT, user_prompt)
        print(f"\n--- [Stage 2 Raw Model Response] ---\n{raw_response}\n------------------------------------\n")
        cleaned = clean_json_string(raw_response)
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as first_err:
        logger.warning(f"Stage 2 JSON parsing failed: {first_err}. Retrying with stricter prompt...")
        retry_sys_prompt = STAGE2_SYSTEM_PROMPT + "\n\nCRITICAL RETRY: Output strictly raw JSON starting with { and ending with }."
        raw_response = call_model_api(client, retry_sys_prompt, user_prompt)
        print(f"\n--- [Stage 2 Retry Raw Model Response] ---\n{raw_response}\n------------------------------------------\n")
        cleaned = clean_json_string(raw_response)
        data = json.loads(cleaned)

    result_map = {}
    clauses_output = data.get("clauses", []) if isinstance(data, dict) else []
    for item in clauses_output:
        if isinstance(item, dict) and "id" in item:
            item_id = item.get("id")
            r_level = str(item.get("risk_level", "medium")).lower().strip()
            if r_level not in ["high", "medium", "low"]:
                r_level = "medium"
            result_map[item_id] = {
                "risk_level": r_level,
                "explanation": item.get("explanation", "").strip()
            }

    return result_map

def compute_overall_risk_score(clauses: list[dict]) -> int:
    """Calculates contract risk score (0-100) based on finalized clause severities."""
    if not clauses:
        return 0

    high_count = sum(1 for c in clauses if c.get("risk_level") == "high")
    med_count = sum(1 for c in clauses if c.get("risk_level") == "medium")
    total = len(clauses)

    weighted_pts = (high_count * 35) + (med_count * 15)
    ratio = (high_count * 1.0 + med_count * 0.45) / total

    score = int((weighted_pts * 0.5) + (ratio * 50))

    if high_count > 0:
        score = max(score, 65)
    elif med_count > 0:
        score = max(score, 35)
    else:
        score = min(score, 20)

    return max(0, min(100, score))

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid request body. Expected JSON with a 'text' field."}), 400

        contract_text = data.get("text", "").strip()
        if not contract_text:
            return jsonify({"error": "Please provide non-empty contract text to analyze."}), 400

        api_key = os.getenv("NEBIUS_API_KEY", "").strip()
        if not api_key:
            return jsonify({
                "error": "NEBIUS_API_KEY is missing or empty in .env. Please configure your API key."
            }), 500

        client = get_openai_client()

        # STAGE 1: Fast Scan
        stage1_clauses = scan_clauses(client, contract_text)
        if not stage1_clauses:
            return jsonify({
                "error": "Could not identify distinct clauses in the provided text."
            }), 400

        # Separate flagged (high/medium) vs low-risk
        flagged_clauses = []
        for idx, clause in enumerate(stage1_clauses):
            if clause["risk_level"] in ["high", "medium"]:
                flagged_clauses.append({
                    "id": idx,
                    "text": clause["text"],
                    "risk_level": clause["risk_level"]
                })

        total_count = len(stage1_clauses)
        flagged_count = len(flagged_clauses)
        fast_tracked_count = total_count - flagged_count

        print(f"\n>> Stage 1: {total_count} clauses scanned. {flagged_count} flagged for deep analysis, {fast_tracked_count} fast-tracked as low-risk.\n")

        # STAGE 2: Deep Analysis (only for flagged clauses)
        stage2_results = {}
        if flagged_clauses:
            stage2_results = deep_analyze(client, flagged_clauses)

        # Merge results back in original order
        final_clauses = []
        for idx, clause in enumerate(stage1_clauses):
            if idx in stage2_results:
                deep_info = stage2_results[idx]
                final_clauses.append({
                    "text": clause["text"],
                    "risk_level": deep_info.get("risk_level", clause["risk_level"]),
                    "explanation": deep_info.get("explanation") or "Identified as requiring caution during detailed review."
                })
            elif clause["risk_level"] in ["high", "medium"]:
                final_clauses.append({
                    "text": clause["text"],
                    "risk_level": clause["risk_level"],
                    "explanation": "Flagged provision with potential legal, financial, or privacy risk."
                })
            else:
                # Fast-tracked low-risk clause
                final_clauses.append({
                    "text": clause["text"],
                    "risk_level": "low",
                    "explanation": "Standard, low-risk clause with standard terms."
                })

        overall_score = compute_overall_risk_score(final_clauses)

        return jsonify({
            "overall_risk_score": overall_score,
            "clauses": final_clauses
        }), 200

    except Exception as e:
        logger.exception("Error during contract analysis pipeline")
        return jsonify({
            "error": f"Analysis pipeline error: {str(e)}"
        }), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
