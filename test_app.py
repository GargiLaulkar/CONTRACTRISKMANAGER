import unittest
from unittest.mock import patch, MagicMock
import json
import os

# Set dummy key for testing
os.environ["NEBIUS_API_KEY"] = "test_mock_key"

from app import app, clean_json_string

class ContractRiskExplainerTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_route(self):
        """Verify home page loads HTML with 200 OK."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Contract Risk Explainer", response.data)
        self.assertIn(b"id=\"contract-input\"", response.data)
        self.assertIn(b"id=\"analyze-btn\"", response.data)

    def test_clean_json_string(self):
        """Verify markdown code fences are stripped properly."""
        raw_md = "```json\n{\"overall_risk_score\": 70, \"clauses\": []}\n```"
        cleaned = clean_json_string(raw_md)
        self.assertEqual(json.loads(cleaned)["overall_risk_score"], 70)

    def test_analyze_empty_input(self):
        """Verify validation error when text is missing or blank."""
        response = self.client.post("/analyze", json={"text": "   "})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    @patch("app.call_nebius_model")
    def test_analyze_success_flow(self, mock_call):
        """Verify end-to-end analyze route with mocked Nebius response."""
        mock_model_output = json.dumps({
            "overall_risk_score": 85,
            "clauses": [
                {
                    "text": "You grant us an irrevocable, perpetual, royalty-free license to all user data.",
                    "risk_level": "high",
                    "explanation": "You forfeit all ongoing rights and control over your uploaded intellectual property."
                },
                {
                    "text": "We may collect anonymous crash logs to diagnose errors.",
                    "risk_level": "low",
                    "explanation": "Standard diagnostic telemetry with no personal data exposure."
                }
            ]
        })
        mock_call.return_value = mock_model_output

        sample_contract = (
            "You grant us an irrevocable, perpetual, royalty-free license to all user data. "
            "We may collect anonymous crash logs to diagnose errors."
        )

        response = self.client.post("/analyze", json={"text": sample_contract})
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["overall_risk_score"], 85)
        self.assertEqual(len(data["clauses"]), 2)
        self.assertEqual(data["clauses"][0]["risk_level"], "high")
        self.assertEqual(data["clauses"][1]["risk_level"], "low")

    @patch("app.call_nebius_model")
    def test_analyze_retry_on_invalid_json(self, mock_call):
        """Verify retry mechanism when first response is malformed."""
        valid_output = json.dumps({
            "overall_risk_score": 50,
            "clauses": [
                {
                    "text": "Either party may terminate upon 30 days notice.",
                    "risk_level": "low",
                    "explanation": "Standard mutual termination clause."
                }
            ]
        })
        # First call returns malformed JSON, second call returns valid JSON
        mock_call.side_effect = ["Not valid JSON response", valid_output]

        response = self.client.post("/analyze", json={"text": "Either party may terminate upon 30 days notice."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_call.call_count, 2)
        data = response.get_json()
        self.assertEqual(data["overall_risk_score"], 50)
        self.assertEqual(len(data["clauses"]), 1)

if __name__ == "__main__":
    unittest.main()
