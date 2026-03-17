# AI Automated Weekly Reporting System

A self-contained Python tool that turns a CSV of weekly business data into a
professional PDF report with AI-generated insights — delivered by email.

Built entirely on **free tools**: Groq (LLM), Gmail SMTP, ReportLab, Streamlit.

---

## Features

| | Feature | Detail |
|---|---|---|
| 📈 | **Historical Tracking** | Saves and visualizes KPI runs over time in `history.csv` |
| 📉 | **Trend Analysis** | 3-week trailing trends, WoW changes, and moving averages |
| 🚨 | **Business Alerts** | Rule-based engine capturing revenue drops and high churn |
| 📊 | **KPI Engine** | Revenue/user/churn growth, ARPU, retention, 3-week MA, trend labels |
| 🤖 | **AI Insights** | Groq API (Llama 3.1) — executive summary, key risks, recommendations |
| ⚠️ | **Anomaly Detection** | Z-score, spike/drop thresholds, trend deviation |
| 📄 | **PDF Report** | ReportLab — professional A4 layout with tables and sections |
| 📊 | **CSV Report** | Structured CSV with KPIs, AI insights, anomaly log, full weekly data |
| 🌐 | **Streamlit UI** | One-page web interface — upload, analyse, download, email |
| 📧 | **Email Delivery** | Gmail SMTP with PDF/CSV attachment, styled HTML body |
| 🔁 | **Fallback Chain** | LLM unavailable → regex extraction → rule-based summary |
| 🔒 | **Secrets** | All credentials in `.env`, never in `config.json` |

---

## Project Structure

```
Weekly Report Generator/
├── app.py                  # Streamlit web UI (main interface)
├── generate_report.py      # CLI entry point
├── config.json             # Non-secret configuration
├── .env                    # Your secrets (never committed)
├── .env.example            # Template for .env
├── requirements.txt
│
├── src/
│   ├── config.py           # Loads config.json + .env → exposes cfg dict
│   ├── logger.py           # Rotating file + console logger
│   ├── kpi_engine.py       # KPIEngine — computes all metrics from DataFrame
│   ├── anomaly_detection.py# AnomalyDetector — z-score, spikes, drops
│   ├── trend_analysis.py   # TrendAnalysis — moving averages, multi-week trends
│   ├── alert_engine.py     # AlertEngine — rules-based business thresholds
│   ├── llm_summary.py      # LLMSummary — Groq API with retry + fallback
│   ├── report_generator.py # generate_pdf() and generate_csv()
│   └── email_sender.py     # EmailSender — Gmail SMTP with attachment
│
├── data/
│   ├── weekly_data.csv     # Input data (week, revenue, users, churn)
│   └── history.csv         # Automatically auto-appends historical KPIs
│
├── reports/                # Generated reports saved here (gitignored)
└── logs/                   # Runtime logs (gitignored)
```

---

## Quick Start

### 1. Clone & set up environment

```bash
git clone https://github.com/your-username/weekly-report-generator.git
cd weekly-report-generator

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```dotenv
GROQ_API_KEY=your_groq_api_key_here        # free at console.groq.com
EMAIL_SENDER=your_gmail@gmail.com          # optional — only needed for email
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx    # Gmail App Password (16 chars)
```

Edit `config.json` to set your company name, model, and thresholds:

```json
{
  "company_name": "My Startup",
  "groq_model": "llama-3.1-8b-instant",
  "report_format": "pdf",
  "email": {
    "recipients": ["ceo@company.com"]
  }
}
```

### 3. Prepare your data

Your CSV must have these columns (header names are case-insensitive):

```csv
week,revenue,users,churn
1,10000,500,0.05
2,12000,540,0.04
```

- `churn` accepts either decimal (`0.05`) or percentage (`5.0`) — auto-normalised
- At least **2 rows** are required to compute growth metrics

---

## Usage

### Streamlit UI (recommended)

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

| Step | Action |
|---|---|
| 1 | Upload your CSV or tick **Use demo data** |
| 2 | Click **▶ Load & Compute KPIs** — cards populate instantly |
| 3 | Click **⚡ Generate** — calls Groq LLM and renders AI insights |
| 4 | Click **⬇ Download PDF** or **⬇ Download CSV** |
| 5 | Enter an email address and click **📤 Send Report** (optional) |

### CLI

```bash
# Generate PDF + CSV, skip email
python generate_report.py --format both --no-email

# Use a specific file, send to a specific address
python generate_report.py --file data/weekly_data.csv --email ceo@co.com --format pdf

# Skip the LLM call (instant, offline-safe)
python generate_report.py --format pdf --no-email --offline
```

| Flag | Default | Description |
|---|---|---|
| `--file PATH` | `config.json → data_file` | CSV input file |
| `--format` | `config.json → report_format` | `pdf` \| `csv` \| `both` |
| `--email ADDRESS` | config recipients | Comma-separated recipient(s) |
| `--no-email` | — | Generate report, skip sending |
| `--offline` | — | Skip LLM; use rule-based fallback summary |
| `--week N` | `0` (latest) | Week offset from end of file |

---

## Getting a Groq API Key (Free)

1. Go to [console.groq.com](https://console.groq.com/) and sign up
2. Navigate to **API Keys** → **Create API Key**
3. Paste it into `.env` as `GROQ_API_KEY=...`

The free tier has generous rate limits — more than sufficient for weekly runs.

---

## Setting Up Gmail App Password (For Email)

1. Enable **2-Step Verification** on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create a new App Password → copy the 16-character code
4. Add to `.env`:
   ```dotenv
   EMAIL_SENDER=your_gmail@gmail.com
   EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```
5. Set `"recipients"` in `config.json`

> Spaces in the App Password are fine — they are stripped automatically before authentication.

---

## Configuration Reference (`config.json`)

```json
{
  "company_name": "My Startup",
  "report_currency": "USD",
  "report_format": "pdf",
  "reports_dir": "reports",
  "data_file": "data/weekly_data.csv",
  "groq_model": "llama-3.1-8b-instant",
  "max_retries": 3,
  "enable_token_tracking": true,
  "email": {
    "sender": "",
    "recipients": [],
    "cc": [],
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465
  },
  "anomaly": {
    "z_score_threshold": 2.0,
    "spike_pct_threshold": 20.0,
    "drop_pct_threshold": -15.0
  },
  "log_level": "INFO"
}
```

| Key | Description |
|---|---|
| `groq_model` | Any Groq-supported model ID |
| `anomaly.z_score_threshold` | Raise to reduce anomaly sensitivity |
| `anomaly.spike_pct_threshold` | Week-over-week % increase flagged as spike |
| `anomaly.drop_pct_threshold` | Week-over-week % drop flagged (negative value) |
| `max_retries` | LLM API retry attempts with exponential back-off |

---

## Architecture

```
Streamlit UI (app.py)  ──or──  CLI (generate_report.py)
         │
         ├── src/config.py           loads config.json + .env
         ├── src/kpi_engine.py       KPIEngine.compute() → KPIResult
         ├── src/anomaly_detection.py AnomalyDetector.detect() → AnomalyReport
         ├── src/llm_summary.py      LLMSummary.generate() → LLMResult
         ├── src/report_generator.py  generate_pdf() / generate_csv()
         └── src/email_sender.py     EmailSender.send()
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `GROQ_API_KEY is not set` | Copy `.env.example` → `.env` and fill in the key |
| `Gmail authentication failed` | Use an App Password, not your regular Gmail password |
| `Need at least 2 weeks of data` | Add more rows to the CSV |
| `model_decommissioned` | Update `groq_model` in `config.json` to a current model |
| Reports re-generate on every click | Expected on first load; subsequent clicks use cached files |

---

## Tech Stack

- **Python 3.11+**
- **Pandas / NumPy** — data processing
- **Groq** — Llama 3.1 LLM (free tier)
- **ReportLab** — PDF generation
- **Streamlit** — web UI
- **smtplib** — email (stdlib)
- **python-dotenv** — environment management
