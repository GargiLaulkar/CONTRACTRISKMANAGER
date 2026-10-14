import os
import io
import json
import re
import logging
import time
from collections import defaultdict
# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, render_template
# pyrefly: ignore [missing-import]
from openai import OpenAI
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

print("GUARD v2 ACTIVE")

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
DEFAULT_ESCALATION_MODEL = "ESCALATION_MODEL_PLACEHOLDER"

# ---------------------------------------------------------------------------
# Abuse-protection constants
# ---------------------------------------------------------------------------
MAX_CHARS = int(os.getenv("MAX_CHARS", "15000"))
MAX_PDF_BYTES = 4 * 1024 * 1024  # 4 MB
MAX_PDF_PAGES = 20
RATE_LIMIT_REQUESTS = 8          # max requests per window
RATE_LIMIT_WINDOW = 3600         # window in seconds (1 hour)

# In-memory store: IP -> list of request timestamps
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# ---------------------------------------------------------------------------
# Guard constants
# ---------------------------------------------------------------------------
MIN_CHARS = 80

# Words that strongly suggest a legal/contractual document
LEGAL_INDICATOR_WORDS = [
    "agree", "agreement", "shall", "party", "parties", "terms", "liability",
    "license", "tenant", "landlord", "lease", "rent", "deposit", "terminate",
    "termination", "confidential", "warrant", "indemnif", "arbitration",
    "governing law", "obligation", "clause", "hereby", "whereas", "fees",
    "payment", "notice", "breach", "consent",
]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
STAGE1_SYSTEM_PROMPT = (
    "You are a fast contract triage analyst. First determine whether the input is a legal document "
    "(contract, lease, NDA, terms of service, policy, etc.).\n"
    "Then split it into individual clauses or provisions and assign a quick preliminary risk_level "
    "('high', 'medium', or 'low') to each clause. Do not include explanations.\n\n"
    "Respond with ONLY a raw JSON object starting with { and ending with }:\n"
    "{\n"
    '  "is_legal_document": true,\n'
    '  "document_type": "NDA | lease | terms of service | ... | not a legal document",\n'
    '  "clauses": [\n'
    '    {"text": "...", "risk_level": "high|medium|low"}\n'
    '  ]\n'
    "}"
)

STAGE2_SYSTEM_PROMPT = (
    "You are an expert contract-risk analyst. For each provided clause, conduct a deep legal analysis.\n"
    "For each clause return:\n"
    "1. 'risk_level': Finalized risk ('high', 'medium', or 'low').\n"
    "2. 'confidence': Your confidence in this assessment ('high' or 'low'). Use 'low' if the clause is ambiguous or context-dependent.\n"
    "3. 'explanation': A concise, one-sentence plain-English explanation of why this clause carries that risk.\n"
    "4. 'suggested_revision': A rewritten, fairer version of that clause that the user could propose in negotiation (or null if low risk).\n\n"
    "Respond with ONLY a raw JSON object starting with { and ending with }:\n"
    "{\n"
    '  "clauses": [\n'
    '    {\n'
    '      "id": 0,\n'
    '      "risk_level": "high|medium|low",\n'
    '      "confidence": "high|low",\n'
    '      "explanation": "...",\n'
    '      "suggested_revision": "..."\n'
    '    }\n'
    '  ]\n'
    "}"
)

ESCALATION_SYSTEM_PROMPT = (
    "You are a Senior Legal Counsel and expert contract-risk auditor. Re-analyze this flagged contract clause with maximum scrutiny.\n"
    "Provide:\n"
    "1. 'risk_level': Finalized assessment ('high', 'medium', or 'low').\n"
    "2. 'explanation': A precise, one-sentence plain-English explanation of the risks.\n"
    "3. 'suggested_revision': A fairer, balanced alternative clause for negotiation.\n\n"
    "Respond with ONLY a raw JSON object starting with { and ending with }:\n"
    "{\n"
    '  "risk_level": "high|medium|low",\n'
    '  "explanation": "...",\n'
    '  "suggested_revision": "..."\n'
    "}"
)

# ---------------------------------------------------------------------------
# Input guard
# ---------------------------------------------------------------------------
def heuristic_is_legal(text: str) -> bool:
    """Returns True if the text contains at least one legal indicator word."""
    lower = text.lower()
    return any(word in lower for word in LEGAL_INDICATOR_WORDS)


def validate_input(text: str) -> "dict | None":
    """Returns None if text passes all pre-checks, or a dict with __status if not."""
    # Character cap
    if len(text) > MAX_CHARS:
        return {
            "__status": 413,
            "error": (
                f"This document is too long for the demo (limit: {MAX_CHARS:,} characters). "
                "Try pasting the most important sections."
            )
        }

    # Minimum length
    if len(text) < MIN_CHARS:
        return {
            "__status": 400,
            "error": "Please paste more text. A contract is usually at least a few sentences long."
        }

    # Heuristic keyword check (no model call)
    if not heuristic_is_legal(text):
        logger.info("GUARD: heuristic found 0 legal indicators -> not_a_contract (no model call)")
        return {
            "__status": 200,
            "not_a_contract": True,
            "document_type": "not a legal document",
            "message": (
                "This doesn't look like a contract or legal agreement, so there's no risk to score. "
                "Try pasting a lease, terms of service, NDA, or similar document."
            )
        }

    return None  # all checks passed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_visitor_ip() -> str:
    """Returns the visitor's IP from X-Forwarded-For (first value) or remote_addr."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def check_rate_limit(ip: str) -> bool:
    """Returns True if the request is allowed; False if limit is exceeded.
    Cleans up expired timestamps on each call so memory doesn't grow.
    """
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    # Prune old timestamps
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > cutoff]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
        return False
    _rate_limit_store[ip].append(now)
    return True


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

def call_model_api(client: OpenAI, system_prompt: str, user_prompt: str, override_model: str = None) -> str:
    """Sends a completion request to Nebius Token Factory with JSON mode & fallback."""
    if override_model:
        model_name = override_model
    else:
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
def scan_clauses(client: OpenAI, contract_text: str) -> tuple[list[dict], "bool | None", str]:
    """Stage 1: Fast triage to split contract into clauses with preliminary risk levels.

    Returns (clauses, is_legal_document, document_type).
    is_legal_document is None when the field is missing from model output.
    """
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

    # Extract is_legal_document and document_type from model output
    if isinstance(data, dict):
        raw_flag = data.get("is_legal_document")  # None if key missing
        is_legal = bool(raw_flag) if raw_flag is not None else None
        document_type = str(data.get("document_type", "unknown")).strip()
        clauses_raw = data.get("clauses", [])
    else:
        is_legal = None
        document_type = "unknown"
        clauses_raw = []

    normalized = []
    for item in clauses_raw:
        if isinstance(item, dict) and item.get("text"):
            r_level = str(item.get("risk_level", "low")).lower().strip()
            if r_level not in ["high", "medium", "low"]:
                r_level = "medium"
            normalized.append({
                "text": item.get("text", "").strip(),
                "risk_level": r_level
            })
    return normalized, is_legal, document_type

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

    user_prompt = (
        "Analyze these flagged contract clauses in detail. Return risk_level, confidence (high/low), "
        "explanation, and suggested_revision for each:\n\n"
        f"{json.dumps(user_payload, indent=2)}"
    )

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

            confidence = str(item.get("confidence", "high")).lower().strip()
            if confidence not in ["high", "low"]:
                confidence = "high"

            result_map[item_id] = {
                "risk_level": r_level,
                "confidence": confidence,
                "explanation": item.get("explanation", "").strip(),
                "suggested_revision": item.get("suggested_revision", None)
            }

    return result_map

# ---------------------------------------------------------------------------
# Stage 3 - Confidence-Based Model Escalation
# ---------------------------------------------------------------------------
def escalate_clause(client: OpenAI, clause: dict) -> dict:
    """Stage 3: Escalates a low-confidence clause to a stronger model."""
    escalation_model = os.getenv("NEBIUS_ESCALATION_MODEL", DEFAULT_ESCALATION_MODEL).strip() or DEFAULT_ESCALATION_MODEL

    # If the user hasn't configured a distinct escalation model yet, fallback gracefully to base model
    if escalation_model == "ESCALATION_MODEL_PLACEHOLDER":
        escalation_model = os.getenv("NEBIUS_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

    user_prompt = f"Conduct an escalated senior legal review on this clause:\n\n\"{clause['text']}\""

    try:
        raw_response = call_model_api(client, ESCALATION_SYSTEM_PROMPT, user_prompt, override_model=escalation_model)
        cleaned = clean_json_string(raw_response)
        data = json.loads(cleaned)
        if isinstance(data, dict):
            r_level = str(data.get("risk_level", clause.get("risk_level", "medium"))).lower().strip()
            if r_level not in ["high", "medium", "low"]:
                r_level = "medium"
            return {
                "risk_level": r_level,
                "explanation": data.get("explanation", clause.get("explanation", "")),
                "suggested_revision": data.get("suggested_revision", clause.get("suggested_revision")),
                "escalated": True
            }
    except Exception as e:
        logger.warning(f"Escalation call failed: {e}. Retaining Stage 2 assessment.")

    return {
        "risk_level": clause.get("risk_level", "medium"),
        "explanation": clause.get("explanation", ""),
        "suggested_revision": clause.get("suggested_revision"),
        "escalated": False
    }

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

def run_analysis_pipeline(contract_text: str, heuristic_hits: int = 0) -> dict:
    """Full multi-stage pipeline: Scan -> Deep Analysis -> Escalation -> Scoring."""
    client = get_openai_client()

    # STAGE 1: Fast Scan
    stage1_clauses, model_is_legal, document_type = scan_clauses(client, contract_text)

    # Guard: model-level not-a-contract check
    # If is_legal_document is explicitly False, short-circuit immediately.
    # If the field was MISSING (None), fall back to heuristic (already passed, so continue).
    model_flag = model_is_legal  # True / False / None
    if model_is_legal is False:
        print(f"GUARD: length_ok=True heuristic_hits={heuristic_hits} model_flag=False -> not_a_contract")
        return {
            "not_a_contract": True,
            "document_type": document_type or "not a legal document",
            "message": (
                "This doesn't look like a contract or legal agreement, so there's no risk to score. "
                "Try pasting a lease, terms of service, NDA, or similar document."
            )
        }
    else:
        print(f"GUARD: length_ok=True heuristic_hits={heuristic_hits} model_flag={model_flag} -> proceed")

    if not stage1_clauses:
        raise ValueError("Could not identify distinct clauses in the provided contract text.")

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

    print(f"\n>> Stage 1: {total_count} clauses scanned. {flagged_count} flagged for deep analysis, {fast_tracked_count} fast-tracked as low-risk.")

    # STAGE 2: Deep Analysis
    stage2_results = {}
    if flagged_clauses:
        stage2_results = deep_analyze(client, flagged_clauses)

    # STAGE 3: Confidence-based Model Escalation
    escalated_count = 0
    escalation_model_name = os.getenv("NEBIUS_ESCALATION_MODEL", DEFAULT_ESCALATION_MODEL)
    final_stage2_results = {}

    for idx_id, clause_info in stage2_results.items():
        original_clause = next((c for c in flagged_clauses if c["id"] == idx_id), None)
        if original_clause and clause_info.get("confidence") == "low":
            logger.info(f"Clause #{idx_id + 1} has low confidence. Escalating to advanced model...")
            escalated_res = escalate_clause(client, {
                "text": original_clause["text"],
                "risk_level": clause_info.get("risk_level", "medium"),
                "explanation": clause_info.get("explanation", ""),
                "suggested_revision": clause_info.get("suggested_revision")
            })
            final_stage2_results[idx_id] = escalated_res
            if escalated_res.get("escalated"):
                escalated_count += 1
        else:
            final_stage2_results[idx_id] = {
                "risk_level": clause_info.get("risk_level", "medium"),
                "explanation": clause_info.get("explanation", ""),
                "suggested_revision": clause_info.get("suggested_revision"),
                "escalated": False
            }

    if escalated_count > 0:
        print(f">> Stage 3: {escalated_count} clause(s) escalated to [{escalation_model_name}] due to low confidence.\n")
    else:
        print(">> Stage 3: High confidence across all deep analyses. 0 clauses escalated.\n")

    # Merge all clauses in original order
    final_clauses = []
    for idx, clause in enumerate(stage1_clauses):
        if idx in final_stage2_results:
            deep_info = final_stage2_results[idx]
            final_clauses.append({
                "text": clause["text"],
                "risk_level": deep_info.get("risk_level", clause["risk_level"]),
                "explanation": deep_info.get("explanation") or "Identified as requiring caution during detailed review.",
                "suggested_revision": deep_info.get("suggested_revision"),
                "escalated": deep_info.get("escalated", False)
            })
        elif clause["risk_level"] in ["high", "medium"]:
            final_clauses.append({
                "text": clause["text"],
                "risk_level": clause["risk_level"],
                "explanation": "Flagged provision with potential legal, financial, or privacy risk.",
                "suggested_revision": None,
                "escalated": False
            })
        else:
            final_clauses.append({
                "text": clause["text"],
                "risk_level": "low",
                "explanation": "Standard, low-risk clause with standard terms.",
                "suggested_revision": None,
                "escalated": False
            })

    overall_score = compute_overall_risk_score(final_clauses)

    return {
        "overall_risk_score": overall_score,
        "stage1_scanned": total_count,
        "stage2_flagged": flagged_count,
        "stage3_escalated": escalated_count,
        "original_text": contract_text,
        "clauses": final_clauses
    }

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

        # Input guard (char cap + min length + heuristic keyword check)
        guard = validate_input(contract_text)
        if guard is not None:
            status = guard.pop("__status", 200)
            logger.info("GUARD blocked /analyze: status=%s", status)
            return jsonify(guard), status

        # Rate limiting: count only requests that pass validate_input
        ip = get_visitor_ip()
        if not check_rate_limit(ip):
            return jsonify({"error": "Demo limit reached. Please try again in a while."}), 429

        # Count heuristic hits for logging inside the pipeline
        lower = contract_text.lower()
        hits = sum(1 for w in LEGAL_INDICATOR_WORDS if w in lower)

        api_key = os.getenv("NEBIUS_API_KEY", "").strip()
        if not api_key:
            return jsonify({
                "error": "NEBIUS_API_KEY is missing or empty in .env. Please configure your API key."
            }), 500

        result = run_analysis_pipeline(contract_text, heuristic_hits=hits)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Error during contract analysis pipeline")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

@app.route("/analyze-pdf", methods=["POST"])
def analyze_pdf():
    try:
        if "file" not in request.files and "pdf" not in request.files:
            return jsonify({"error": "No PDF file uploaded. Please select a .pdf file."}), 400

        uploaded_file = request.files.get("file") or request.files.get("pdf")
        if not uploaded_file or uploaded_file.filename == "":
            return jsonify({"error": "No selected file. Please upload a valid PDF."}), 400

        file_bytes = uploaded_file.read()
        if not file_bytes:
            return jsonify({"error": "Uploaded PDF file is empty."}), 400

        # File size cap (4 MB)
        if len(file_bytes) > MAX_PDF_BYTES:
            return jsonify({
                "error": "This PDF exceeds the 4 MB demo limit. Please upload a smaller file or paste the text directly."
            }), 413

        # Page count cap (check before extracting text)
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            num_pages = len(reader.pages)
            if num_pages > MAX_PDF_PAGES:
                return jsonify({
                    "error": f"This PDF has {num_pages} pages which exceeds the {MAX_PDF_PAGES}-page demo limit. "
                             "Try uploading a shorter document or paste the key sections instead."
                }), 413

            extracted_text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + "\n"
        except Exception as pdf_err:
            logger.warning(f"pypdf extraction error: {pdf_err}")
            extracted_text = ""

        extracted_text = extracted_text.strip()
        if not extracted_text:
            return jsonify({
                "error": "Could not extract text from this PDF. Try pasting the text directly instead."
            }), 400

        # Input guard (char cap + min length + heuristic keyword check)
        guard = validate_input(extracted_text)
        if guard is not None:
            status = guard.pop("__status", 200)
            logger.info("GUARD blocked /analyze-pdf: status=%s", status)
            return jsonify(guard), status

        # Rate limiting: count only requests that pass validate_input
        ip = get_visitor_ip()
        if not check_rate_limit(ip):
            return jsonify({"error": "Demo limit reached. Please try again in a while."}), 429

        api_key = os.getenv("NEBIUS_API_KEY", "").strip()
        if not api_key:
            return jsonify({
                "error": "NEBIUS_API_KEY is missing or empty in .env. Please configure your API key."
            }), 500

        lower = extracted_text.lower()
        hits = sum(1 for w in LEGAL_INDICATOR_WORDS if w in lower)

        logger.info("Extracted %d characters from uploaded PDF: %s", len(extracted_text), uploaded_file.filename)
        result = run_analysis_pipeline(extracted_text, heuristic_hits=hits)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Error during PDF analysis pipeline")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
