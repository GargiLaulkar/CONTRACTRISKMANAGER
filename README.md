# Contract Risk Explainer ⚖️

A high-performance web application that parses legal contracts, Terms of Service, NDAs, and privacy policies into individual clauses, evaluates their risk levels (High, Medium, Low), and provides plain-English explanations, fair revision suggestions, and an overall risk score.

Powered by a **multi-stage AI pipeline** combining **NVIDIA Nemotron** models on **Nebius Token Factory**, **Flask**, and modern responsive web technologies.

---

## 🌟 Recent Improvements & Advanced Capabilities

### 1. ✍️ Suggested Fairer Clause Rewrites
For every clause flagged as **High** or **Medium** risk, the analysis engine automatically generates a rewritten, balanced version (`suggested_revision`). Users can copy this wording directly into negotiations to replace aggressive or one-sided terms with industry-standard compromises.

### 2. ⚡ Confidence-Based Model Escalation (Stage 3)
During deep clause analysis, the model reports a confidence score (`high` or `low`). If any complex, ambiguous, or jurisdiction-specific clause triggers `low` confidence, the system automatically escalates that individual clause to a senior frontier reasoning model (`NEBIUS_ESCALATION_MODEL`). Escalated clauses receive enhanced scrutiny and are marked with a verified audit badge.

### 3. 📊 Mini Evaluation Benchmark (`eval.py`)
To objectively measure classification accuracy, the project includes a standalone benchmark suite ([`eval.py`](file:///c:/CONTRACTRISKMANAGER/eval.py)) paired with a hand-labeled dataset ([`eval_set.json`](file:///c:/CONTRACTRISKMANAGER/eval_set.json)) of 15 diverse contract provisions (liability waivers, non-competes, auto-renewals, payment terms, and force majeure). Running `python eval.py` produces an automated pass/fail report with precision metrics.

### 4. 📄 Direct PDF Document Upload
Users are no longer limited to pasting raw text. Contracts and agreement PDFs can be directly uploaded via the **"Upload PDF"** button. The server extracts the text using `pypdf` and processes the full document through the multi-stage pipeline.

---

## 🏗️ Multi-Stage Pipeline Architecture

1. **Stage 1 (Fast Scan - `scan_clauses`)**: Rapid triage using `NVIDIA Nemotron-3-Nano` to segment the contract into clauses and assign preliminary risk tiers.
2. **Stage 2 (Deep Analysis - `deep_analyze`)**: Flags risky clauses for in-depth evaluation and negotiation rewrite generation, while fast-tracking low-risk clauses to minimize latency and token spend.
3. **Stage 3 (Escalation - `escalate_clause`)**: Dynamic model routing that escalates low-confidence edge cases to advanced reasoning models.
4. **Scoring & Rendering**: Merges clauses in original sequence, calculates a weighted 0–100 risk gauge, and renders interactive risk cards.

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file from `.env.example`:
```env
NEBIUS_API_KEY=your_actual_nebius_api_key_here
NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
NEBIUS_ESCALATION_MODEL=ESCALATION_MODEL_PLACEHOLDER
```

---

## ▶️ Running the Application

### Start the Web Application
```bash
python app.py
```
Visit `http://127.0.0.1:5000` in your browser.

### Run the Evaluation Benchmark
```bash
python eval.py
```

---

## 📁 Project Structure

```
CONTRACTRISKMANAGER/
├── app.py                 # Multi-stage Flask backend (Scan, Deep Analyze, Escalation, PDF extraction)
├── eval.py                # Standalone evaluation benchmark runner
├── eval_set.json          # 15 hand-labeled test clauses with expected risk classifications
├── requirements.txt       # Dependencies (flask, openai, python-dotenv, pypdf)
├── .env.example           # Example environment template
├── README.md              # Project documentation & improvements
├── templates/
│   └── index.html         # Responsive web UI with PDF upload & negotiation cards
└── static/
    ├── style.css          # Dark-mode styling, risk color tokens, and revision boxes
    └── script.js          # Interactive frontend logic & API communication
```
