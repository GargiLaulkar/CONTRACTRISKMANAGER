# Contract Risk Explainer ⚖️

A clean, responsive web application that parses legal contracts, Terms of Service, NDAs, and privacy policies into individual clauses, evaluates their risk levels (High, Medium, Low), and provides plain-English explanations along with an overall contract risk score.

Powered by **Flask** on the backend, **Vanilla HTML/CSS/JS** on the frontend, and the **Nebius Token Factory API** (OpenAI-compatible) for AI analysis.

---

## 🚀 Features

- **Clause-by-Clause Parsing**: Breaks lengthy legal text into distinct provisions.
- **Risk Assessment**: Color-coded risk levels (Red for High, Yellow for Medium, Green for Low).
- **Plain-English Explanations**: Simple summaries explaining why each clause is risky.
- **Overall Risk Gauge**: Numerical risk score (0-100) and severity classification.
- **Quick Sample Loaders**: Test instantly with pre-built Terms of Service and NDA snippets.
- **Filtering**: View all clauses or filter specifically by risk level.
- **Robust Error Handling**: Gracefully handles network issues, missing keys, and model retry parsing.

---

## 🛠️ Installation & Setup

### 1. Clone or Open Workspace
Ensure you are in the project root directory:
```bash
cd CONTRACTRISKMANAGER
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file from the `.env.example` template:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Open `.env` and fill in your Nebius API Key and model identifier:
```env
NEBIUS_API_KEY=your_actual_nebius_api_key_here
NEBIUS_MODEL=your_model_id_here
```

---

## ▶️ Running the Application

Start the Flask development server:
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📁 Project Structure

```
CONTRACTRISKMANAGER/
├── app.py                 # Single-file Flask backend with /analyze route & Nebius OpenAI client
├── requirements.txt       # Dependencies (flask, openai, python-dotenv)
├── .env.example           # Example environment file
├── README.md              # Setup & running instructions
├── templates/
│   └── index.html         # Frontend HTML structure
└── static/
    ├── style.css          # Modern dark-mode styling & risk color tokens
    └── script.js          # Interactive frontend logic & API communication
```
