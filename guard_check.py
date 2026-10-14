"""
guard_check.py - Proves the GUARD v2 system works without real API calls.
Run with:  python guard_check.py
"""

import json
import os
import sys
import unittest.mock as mock

os.environ.setdefault("NEBIUS_API_KEY", "test_dummy_key")
os.environ.setdefault("NEBIUS_MODEL", "test-model")

MOCK_STAGE1_TOS = json.dumps({
    "is_legal_document": True,
    "document_type": "terms of service",
    "clauses": [
        {"text": "You grant us an irrevocable, perpetual, royalty-free license to all uploaded content.", "risk_level": "high"},
        {"text": "We may terminate this agreement at any time without notice.", "risk_level": "high"},
        {"text": "Any disputes shall be resolved by binding arbitration.", "risk_level": "medium"},
        {"text": "You indemnify us from all claims arising from your use of the service.", "risk_level": "high"},
        {"text": "The governing law of this agreement is the State of Delaware.", "risk_level": "low"},
        {"text": "Liability is limited to the amount paid in the last 12 months.", "risk_level": "medium"},
    ]
})

MOCK_STAGE2_TOS = json.dumps({
    "clauses": [
        {"id": 0, "risk_level": "high", "confidence": "high", "explanation": "Irrevocable license is aggressive.", "suggested_revision": "Grant a limited, revocable license."},
        {"id": 1, "risk_level": "high", "confidence": "high", "explanation": "No-notice termination is one-sided.", "suggested_revision": "Termination requires 30 days written notice."},
        {"id": 2, "risk_level": "medium", "confidence": "high", "explanation": "Binding arbitration limits legal recourse.", "suggested_revision": "Disputes may be resolved by arbitration or court."},
        {"id": 3, "risk_level": "high", "confidence": "high", "explanation": "Broad indemnification exposes the user.", "suggested_revision": "Indemnification is limited to gross negligence."},
        {"id": 5, "risk_level": "medium", "confidence": "high", "explanation": "Liability cap may be insufficient.", "suggested_revision": "Liability limited to greater of fees paid or $100."},
    ]
})

def make_fake_response(content):
    msg = mock.MagicMock()
    msg.content = content
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp

import importlib
import app as app_module
importlib.reload(app_module)
flask_app = app_module.app
flask_app.testing = True
client = flask_app.test_client()

model_call_count = [0]
original_call_model_api = app_module.call_model_api

def counting_call_model_api(*args, **kwargs):
    model_call_count[0] += 1
    return original_call_model_api(*args, **kwargs)

# TEST 1
print("=" * 60)
print("TEST 1: 'hello' -> HTTP 400 (min-length), no model call")
print("=" * 60)
model_call_count[0] = 0
with mock.patch.object(app_module, "call_model_api", side_effect=counting_call_model_api):
    resp = client.post("/analyze", json={"text": "hello"}, content_type="application/json")
data1 = resp.get_json()
print(f"  Status : {resp.status_code}")
print(f"  Body   : {data1}")
print(f"  Model calls: {model_call_count[0]}")
t1_status_ok = resp.status_code == 400
t1_error_ok = "error" in (data1 or {}) and "paste more text" in (data1.get("error") or "").lower()
t1_no_model = model_call_count[0] == 0
print(f"  -> status==400: {t1_status_ok}")
print(f"  -> paste more text in error: {t1_error_ok}")
print(f"  -> model NOT called: {t1_no_model}")
t1 = t1_status_ok and t1_error_ok and t1_no_model
print(f"  RESULT: {'PASS' if t1 else 'FAIL'}\n")

# TEST 2
MONSOON_TEXT = (
    "Heavy monsoon rains lashed the coastal districts on Tuesday as the weather department "
    "issued red alerts for several areas. Residents were asked to stay indoors while rescue "
    "teams were deployed. Schools and colleges were closed for the day. The river is expected "
    "to swell further as upstream regions continue to receive heavy rainfall throughout the week. "
    "Farmers are worried about the damage to standing crops."
)
print("=" * 60)
print("TEST 2: Monsoon paragraph -> not_a_contract (heuristic), no model call")
print("=" * 60)
print(f"  Text length: {len(MONSOON_TEXT)} chars")
model_call_count[0] = 0
with mock.patch.object(app_module, "call_model_api", side_effect=counting_call_model_api):
    resp = client.post("/analyze", json={"text": MONSOON_TEXT}, content_type="application/json")
data2 = resp.get_json()
print(f"  Status : {resp.status_code}")
print(f"  Body   : {data2}")
print(f"  Model calls: {model_call_count[0]}")
t2_status_ok = resp.status_code == 200
t2_not_contract = (data2 or {}).get("not_a_contract") is True
t2_no_model = model_call_count[0] == 0
print(f"  -> status==200: {t2_status_ok}")
print(f"  -> not_a_contract==True: {t2_not_contract}")
print(f"  -> model NOT called: {t2_no_model}")
t2 = t2_status_ok and t2_not_contract and t2_no_model
print(f"  RESULT: {'PASS' if t2 else 'FAIL'}\n")

# TEST 3
TOS_TEXT = """Terms of Service Agreement

1. License Grant. You grant us an irrevocable, perpetual, royalty-free license to all uploaded content.

2. Termination. We may terminate this agreement at any time without notice, for any reason.

3. Arbitration. Any disputes shall be resolved by binding arbitration under AAA rules.
   The parties hereby waive their right to a jury trial.

4. Indemnification. You shall indemnify, defend, and hold harmless the Company from all claims
   arising from your use of the service.

5. Governing Law. The governing law of this agreement is the State of Delaware.

6. Liability Cap. Liability is limited to the amount paid in the last 12 months.
"""
print("=" * 60)
print("TEST 3: Real ToS text -> normal analysis (model mocked)")
print("=" * 60)
print(f"  Text length: {len(TOS_TEXT)} chars")
model_call_count[0] = 0
call_responses = [MOCK_STAGE1_TOS, MOCK_STAGE2_TOS]
call_index = [0]

def fake_call_model_api(*args, **kwargs):
    model_call_count[0] += 1
    idx = min(call_index[0], len(call_responses) - 1)
    call_index[0] += 1
    return call_responses[idx]

with mock.patch.object(app_module, "call_model_api", side_effect=fake_call_model_api):
    resp = client.post("/analyze", json={"text": TOS_TEXT}, content_type="application/json")
data3 = resp.get_json()
print(f"  Status : {resp.status_code}")
print(f"  Model calls: {model_call_count[0]}")
if data3:
    print(f"  overall_risk_score: {data3.get('overall_risk_score')}")
    print(f"  clauses count     : {len(data3.get('clauses', []))}")
    print(f"  stage1_scanned    : {data3.get('stage1_scanned')}")
    print(f"  not_a_contract    : {data3.get('not_a_contract', 'KEY ABSENT (correct)')}")
t3_status_ok = resp.status_code == 200
t3_has_score = isinstance((data3 or {}).get("overall_risk_score"), int)
t3_has_clauses = len((data3 or {}).get("clauses", [])) > 0
t3_not_flagged = not (data3 or {}).get("not_a_contract", False)
t3_model_called = model_call_count[0] >= 1
print(f"  -> status==200: {t3_status_ok}")
print(f"  -> has overall_risk_score: {t3_has_score}")
print(f"  -> has clauses: {t3_has_clauses}")
print(f"  -> not_a_contract absent/False: {t3_not_flagged}")
print(f"  -> model was called: {t3_model_called}")
t3 = t3_status_ok and t3_has_score and t3_has_clauses and t3_not_flagged and t3_model_called
print(f"  RESULT: {'PASS' if t3 else 'FAIL'}\n")

print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Test 1 (min-length block)       : {'PASS' if t1 else 'FAIL'}")
print(f"  Test 2 (heuristic not-contract) : {'PASS' if t2 else 'FAIL'}")
print(f"  Test 3 (real contract analysis) : {'PASS' if t3 else 'FAIL'}")
all_pass = t1 and t2 and t3
print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME TESTS FAILED'}")
sys.exit(0 if all_pass else 1)
