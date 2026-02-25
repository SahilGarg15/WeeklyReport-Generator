"""
app.py
───────
AI Weekly Report Generator — Streamlit UI

Run:
    streamlit run app.py
"""

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────
st.set_page_config(
    page_title="Weekly Report Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"]          { background: #161b27; border-right: 1px solid #1f2937; }

/* ── KPI Cards ── */
.kpi-card {
    background: #1a2035;
    border: 1px solid #1f2d4a;
    border-radius: 10px;
    padding: 18px 20px 14px;
    text-align: center;
    margin-bottom: 4px;
}
.kpi-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: #6b7fa3;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 26px;
    font-weight: 700;
    color: #e2e8f0;
    line-height: 1.1;
}
.kpi-delta-pos { font-size: 13px; color: #34d399; margin-top: 4px; }
.kpi-delta-neg { font-size: 13px; color: #f87171; margin-top: 4px; }
.kpi-delta-neu { font-size: 13px; color: #94a3b8; margin-top: 4px; }

/* ── Section headers ── */
.section-header {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4b83c0;
    padding: 6px 0 4px;
    border-bottom: 1px solid #1f2d4a;
    margin-bottom: 16px;
}

/* ── Insight boxes ── */
.insight-box {
    background: #1a2035;
    border-left: 3px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin-bottom: 10px;
    color: #cbd5e1;
    font-size: 15px;
    line-height: 1.6;
}
.risk-box {
    background: #1e1a2e;
    border-left: 3px solid #f59e0b;
    border-radius: 0 8px 8px 0;
    padding: 10px 16px;
    margin-bottom: 6px;
    color: #e2c97e;
    font-size: 14px;
}
.rec-box {
    background: #17201a;
    border-left: 3px solid #34d399;
    border-radius: 0 8px 8px 0;
    padding: 10px 16px;
    margin-bottom: 6px;
    color: #86efac;
    font-size: 14px;
}
.outlook-box {
    background: #1a1f2e;
    border: 1px solid #2d3a56;
    border-radius: 8px;
    padding: 12px 18px;
    color: #93c5fd;
    font-size: 14px;
    font-style: italic;
}
.anomaly-row {
    background: #1f1a1a;
    border-left: 3px solid #f97316;
    border-radius: 0 6px 6px 0;
    padding: 8px 14px;
    margin-bottom: 5px;
    color: #fdba74;
    font-size: 13px;
}

/* ── Status badge ── */
.badge-ok   { background:#14532d; color:#86efac; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:700; }
.badge-warn { background:#451a03; color:#fdba74; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:700; }

/* ── Divider ── */
hr { border: none; border-top: 1px solid #1f2937; margin: 24px 0; }

/* ── Download buttons ── */
[data-testid="stDownloadButton"] > button {
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: 0.03em;
}

/* Hide Streamlit branding */
#MainMenu, footer, [data-testid="stStatusWidget"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────

def _delta_class(value_str: str) -> str:
    """Return CSS class based on sign of a formatted value like '+14.3%'."""
    if value_str.startswith("+"):
        return "kpi-delta-pos"
    if value_str.startswith("-"):
        return "kpi-delta-neg"
    return "kpi-delta-neu"


def kpi_card(label: str, value: str, delta: str | None = None) -> str:
    delta_html = ""
    if delta:
        cls = _delta_class(delta)
        arrows = {"kpi-delta-pos": "▲", "kpi-delta-neg": "▼", "kpi-delta-neu": "→"}
        delta_html = f'<div class="{cls}">{arrows[cls]} {delta}</div>'
    return f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  {delta_html}
</div>"""


def section(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# ── Session state init ────────────────────────────────────────────
for key in ("df", "kpi_result", "kpi_payload", "full_df",
            "anomaly_report", "llm_result", "pdf_path", "csv_path"):
    if key not in st.session_state:
        st.session_state[key] = None


# ═══════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    # Company name override
    from src.config import cfg
    default_company = cfg.get("company_name", "My Startup")
    company_name = st.text_input("Company Name", value=default_company)

    st.markdown("---")

    # CSV Upload
    st.markdown("### 📂 Data Source")
    uploaded = st.file_uploader(
        "Upload weekly_data.csv",
        type=["csv"],
        help="Columns required: week, revenue, users, churn",
    )

    use_demo = st.checkbox("Use demo data", value=(uploaded is None))

    if st.button("▶  Load & Compute KPIs", width="stretch", type="primary"):
        with st.spinner("Computing KPIs…"):
            try:
                from src.kpi_engine import KPIEngine
                from src.anomaly_detection import AnomalyDetector

                if uploaded is not None:
                    df = pd.read_csv(uploaded)
                elif use_demo:
                    demo_path = Path(cfg["data_file"])
                    if not demo_path.exists():
                        st.error(f"Demo file not found: {demo_path}")
                        st.stop()
                    df = pd.read_csv(demo_path)
                else:
                    st.error("Upload a CSV or enable demo data.")
                    st.stop()

                engine = KPIEngine(df)
                kpi_result = engine.compute()
                full_df = engine.full_summary_df()
                kpi_payload = kpi_result.to_prompt_payload()

                detector = AnomalyDetector(df)
                anomaly_report = detector.detect(metrics=["revenue", "users"])

                st.session_state.df           = df
                st.session_state.kpi_result   = kpi_result
                st.session_state.kpi_payload  = kpi_payload
                st.session_state.full_df      = full_df
                st.session_state.anomaly_report = anomaly_report
                st.session_state.llm_result   = None  # reset on new data
                st.session_state.pdf_path     = None
                st.session_state.csv_path     = None
                st.success("✓ KPIs computed")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    # Email section
    st.markdown("### 📧 Email Delivery")
    email_recipients = st.text_input(
        "Recipient(s)",
        placeholder="ceo@company.com, team@company.com",
        help="Comma-separated email addresses",
    )

    send_email_btn = st.button(
        "📤  Send Report",
        width="stretch",
        disabled=(st.session_state.pdf_path is None),
    )

    if send_email_btn and st.session_state.pdf_path:
        with st.spinner("Sending email…"):
            try:
                from src.email_sender import EmailSender
                sender = EmailSender()
                recipients_list = (
                    [r.strip() for r in email_recipients.split(",") if r.strip()]
                    if email_recipients else None
                )
                llm_for_email = st.session_state.llm_result
                if llm_for_email is None:
                    from src.llm_summary import LLMSummary
                    llm_for_email = LLMSummary._fallback(
                        st.session_state.kpi_payload, "no AI summary generated"
                    )
                ok = sender.send(
                    attachment_path=st.session_state.pdf_path,
                    week=str(st.session_state.kpi_result.current_week),
                    kpi_payload=st.session_state.kpi_payload,
                    llm_result=llm_for_email,
                    recipients=recipients_list,
                )
                if ok:
                    st.success("✓ Email sent!")
                else:
                    st.error("Email failed — check logs.")
            except Exception as e:
                st.error(f"Email error: {e}")

    # Model info
    st.markdown("---")
    st.caption(f"Model: `{cfg.get('groq_model', 'N/A')}`")
    st.caption("Powered by Groq · Free tier")


# ═══════════════════════════════════════════════════════════════════
# MAIN AREA
# ═══════════════════════════════════════════════════════════════════

# ── Header ────────────────────────────────────────────────────────
col_title, col_badge = st.columns([5, 1])
with col_title:
    week_label = ""
    if st.session_state.kpi_result:
        week_label = f" — Week {st.session_state.kpi_result.current_week}"
    st.markdown(
        f"<h1 style='color:#e2e8f0;font-size:28px;font-weight:800;"
        f"letter-spacing:.02em;margin:0'>"
        f"📊 {company_name.upper()}{week_label}</h1>",
        unsafe_allow_html=True,
    )
    st.caption("AI-Powered Weekly Business Intelligence Report")

with col_badge:
    if st.session_state.kpi_result:
        st.markdown(
            '<div style="text-align:right;padding-top:14px">'
            '<span class="badge-ok">● LIVE</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="text-align:right;padding-top:14px">'
            '<span class="badge-warn">● AWAITING DATA</span></div>',
            unsafe_allow_html=True,
        )

st.markdown("<hr>", unsafe_allow_html=True)

# ── KPI Cards ─────────────────────────────────────────────────────
section("📊 KPI Overview")

if st.session_state.kpi_result is None:
    st.markdown(
        "<p style='color:#475569;font-size:14px;padding:20px 0'>"
        "Upload a CSV and click <b>Load &amp; Compute KPIs</b> to get started.</p>",
        unsafe_allow_html=True,
    )
else:
    p = st.session_state.kpi_payload
    r = st.session_state.kpi_result

    row1 = st.columns(4)
    row2 = st.columns(4)

    cards_row1 = [
        ("Revenue",         p["revenue"],         p["revenue_growth"]),
        ("Users",           p["users"],            p["user_growth"]),
        ("Churn Rate",      p["churn_rate"],       p["churn_change"]),
        ("ARPU",            p["arpu"],             None),
    ]
    cards_row2 = [
        ("Retention Rate",  p["retention_rate"],   None),
        ("3-Wk Rev Avg",   p["revenue_ma3"],       None),
        ("Total Revenue",   p["total_revenue"],     None),
        ("Total Weeks",     p["total_weeks"],       None),
    ]

    for col, (label, value, delta) in zip(row1, cards_row1):
        with col:
            st.markdown(kpi_card(label, value, delta), unsafe_allow_html=True)

    for col, (label, value, delta) in zip(row2, cards_row2):
        with col:
            st.markdown(kpi_card(label, value, delta), unsafe_allow_html=True)

    # Trend row
    st.markdown("<br>", unsafe_allow_html=True)
    tc1, tc2, tc3, tc4 = st.columns(4)
    trend_map = {
        "up":        ("↑ Uptrend",    "#34d399"),
        "down":      ("↓ Downtrend",  "#f87171"),
        "stable":    ("→ Stable",     "#94a3b8"),
        "improving": ("↑ Improving",  "#34d399"),
        "worsening": ("↓ Worsening",  "#f87171"),
    }

    def trend_html(label, trend_key):
        text, color = trend_map.get(trend_key, ("–", "#94a3b8"))
        return (
            f"<div style='text-align:center'>"
            f"<span style='font-size:11px;color:#6b7fa3;text-transform:uppercase;"
            f"letter-spacing:.07em'>{label}</span><br>"
            f"<span style='font-size:15px;font-weight:700;color:{color}'>{text}</span>"
            f"</div>"
        )

    with tc1:
        st.markdown(trend_html("Revenue Trend",   r.revenue_trend), unsafe_allow_html=True)
    with tc2:
        st.markdown(trend_html("User Trend",      r.user_trend),    unsafe_allow_html=True)
    with tc3:
        st.markdown(trend_html("Churn Trend",     r.churn_trend),   unsafe_allow_html=True)
    with tc4:
        st.markdown(
            f"<div style='text-align:center'>"
            f"<span style='font-size:11px;color:#6b7fa3;text-transform:uppercase;"
            f"letter-spacing:.07em'>Peak Week</span><br>"
            f"<span style='font-size:15px;font-weight:700;color:#e2e8f0'>"
            f"Week {r.peak_revenue_week}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Data Preview ──────────────────────────────────────────────
    with st.expander("🗂  Full Weekly Data Table", expanded=False):
        display_df = st.session_state.full_df.copy()
        display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]
        st.dataframe(display_df, hide_index=True, width="stretch")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Anomalies ─────────────────────────────────────────────────
    section("⚠ Anomaly Detection")
    ar = st.session_state.anomaly_report
    if ar and ar.has_anomalies:
        for line in ar.summary_lines():
            st.markdown(
                f'<div class="anomaly-row">⚠&nbsp; {line}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="color:#4ade80;font-size:14px;padding:6px 0">'
            '✓ No statistical anomalies detected.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── AI Insights ───────────────────────────────────────────────
    section("🤖 AI Insights")

    ai_col, btn_col = st.columns([5, 1])
    with btn_col:
        gen_btn = st.button("⚡ Generate", type="primary", width="stretch")
    with ai_col:
        st.markdown(
            "<p style='color:#475569;font-size:13px;padding-top:6px'>"
            "Click to call Groq LLM and generate the executive summary, risks & recommendations.</p>",
            unsafe_allow_html=True,
        )

    if gen_btn:
        with st.spinner("Calling Groq LLM…"):
            try:
                from src.llm_summary import LLMSummary
                llm = LLMSummary()
                anomaly_lines = ar.summary_lines() if ar else []
                result = llm.generate(st.session_state.kpi_payload, anomaly_lines)
                st.session_state.llm_result = result
                st.session_state.pdf_path = None   # reset so downloads reflect new insight
                st.session_state.csv_path = None
            except Exception as e:
                st.error(f"LLM error: {e}")

    if st.session_state.llm_result:
        lr = st.session_state.llm_result

        # Executive Summary
        st.markdown(
            f'<div class="insight-box">{lr.executive_summary}</div>',
            unsafe_allow_html=True,
        )

        ins_left, ins_right = st.columns(2)

        with ins_left:
            st.markdown(
                "<p style='font-size:12px;font-weight:700;color:#f59e0b;"
                "text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px'>"
                "⚡ Key Risks</p>",
                unsafe_allow_html=True,
            )
            for risk in lr.key_risks:
                st.markdown(
                    f'<div class="risk-box">• {risk}</div>',
                    unsafe_allow_html=True,
                )

        with ins_right:
            st.markdown(
                "<p style='font-size:12px;font-weight:700;color:#34d399;"
                "text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px'>"
                "✅ Recommendations</p>",
                unsafe_allow_html=True,
            )
            for i, rec in enumerate(lr.recommendations, 1):
                st.markdown(
                    f'<div class="rec-box">{i}. {rec}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="outlook-box">🔭 <b>Outlook:</b> {lr.outlook}</div>',
            unsafe_allow_html=True,
        )

        # Token info
        st.markdown(
            f"<p style='font-size:11px;color:#334155;margin-top:10px'>"
            f"Model: {lr.model} &nbsp;·&nbsp; "
            f"Tokens: {lr.total_tokens} &nbsp;·&nbsp; "
            f"Latency: {lr.latency_seconds}s</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='color:#334155;font-size:13px;padding:10px 0'>"
            "AI summary not yet generated. Click <b>⚡ Generate</b>.</p>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Download Report ───────────────────────────────────────────
    section("📄 Download Report")

    dl_left, dl_right, *_ = st.columns([2, 2, 4])

    # --- Generate PDF bytes (cached in session state) ---
    def _ensure_pdf() -> bytes | None:
        if st.session_state.pdf_path and Path(st.session_state.pdf_path).exists():
            return _read_bytes(st.session_state.pdf_path)
        try:
            from src.report_generator import generate_pdf
            llm = st.session_state.llm_result
            if llm is None:
                from src.llm_summary import LLMSummary
                llm = LLMSummary._fallback(st.session_state.kpi_payload, "no LLM")
            out = generate_pdf(
                st.session_state.kpi_payload,
                llm,
                st.session_state.anomaly_report,
                company_name=company_name,
            )
            st.session_state.pdf_path = out
            return _read_bytes(out)
        except Exception as e:
            st.error(f"PDF generation error: {e}")
            return None

    def _ensure_csv() -> bytes | None:
        if st.session_state.csv_path and Path(st.session_state.csv_path).exists():
            return _read_bytes(st.session_state.csv_path)
        try:
            from src.report_generator import generate_csv
            llm = st.session_state.llm_result
            if llm is None:
                from src.llm_summary import LLMSummary
                llm = LLMSummary._fallback(st.session_state.kpi_payload, "no LLM")
            out = generate_csv(
                st.session_state.kpi_payload,
                llm,
                st.session_state.anomaly_report,
                full_df=st.session_state.full_df,
            )
            st.session_state.csv_path = out
            return _read_bytes(out)
        except Exception as e:
            st.error(f"CSV generation error: {e}")
            return None

    with dl_left:
        pdf_bytes = _ensure_pdf()
        if pdf_bytes:
            from datetime import datetime
            fname = f"weekly_report_{datetime.now().strftime('%Y_%m_%d')}.pdf"
            st.download_button(
                label="⬇  Download PDF",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                width="stretch",
            )
        else:
            st.button("⬇  Download PDF", disabled=True, width="stretch")

    with dl_right:
        csv_bytes = _ensure_csv()
        if csv_bytes:
            from datetime import datetime
            fname = f"weekly_report_{datetime.now().strftime('%Y_%m_%d')}.csv"
            st.download_button(
                label="⬇  Download CSV",
                data=csv_bytes,
                file_name=fname,
                mime="text/csv",
                width="stretch",
            )
        else:
            st.button("⬇  Download CSV", disabled=True, width="stretch")

    st.markdown(
        "<p style='font-size:12px;color:#334155;margin-top:6px'>"
        "Reports are also saved to <code>reports/</code> in the project folder.</p>",
        unsafe_allow_html=True,
    )


# ── Placeholder when no data ──────────────────────────────────────
if st.session_state.kpi_result is None:
    st.markdown("""
<div style="text-align:center;padding:80px 0 60px">
  <div style="font-size:56px;margin-bottom:16px">📊</div>
  <div style="font-size:22px;font-weight:700;color:#334155;margin-bottom:10px">
    No data loaded yet
  </div>
  <div style="font-size:15px;color:#1e293b;max-width:400px;margin:0 auto">
    Upload your <code>weekly_data.csv</code> in the sidebar, or enable
    <b>Use demo data</b>, then click <b>▶ Load &amp; Compute KPIs</b>.
  </div>
</div>
""", unsafe_allow_html=True)
