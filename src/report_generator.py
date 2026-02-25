"""
src/report_generator.py
────────────────────────
Report Generation Module — PDF and CSV output.

PDF layout
───────────
  1. Header  (company name, report date, week)
  2. KPI Summary Table
  3. Executive Summary
  4. Key Risks
  5. Strategic Recommendations
  6. Anomaly Section (if any)
  7. Outlook
  8. Footer (model, tokens, timestamp)

Output filename: weekly_report_YYYY_MM_DD.pdf / .csv
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import cfg
from src.logger import get_logger

logger = get_logger(__name__)


def _reports_dir() -> Path:
    d = Path(cfg["reports_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def _filename(ext: str) -> str:
    date_str = datetime.now().strftime("%Y_%m_%d")
    return f"weekly_report_{date_str}.{ext}"


# ─────────────────────────────────────────────────────────────────
# PDF Report
# ─────────────────────────────────────────────────────────────────

def generate_pdf(
    kpi_payload: dict[str, str],
    llm_result: Any,
    anomaly_report: Any,
    company_name: str | None = None,
    out_path: str | Path | None = None,
) -> Path:
    """
    Build a professional PDF report using ReportLab.

    Returns the absolute path of the generated file.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    company = company_name or cfg.get("company_name", "My Startup")
    dest = Path(out_path) if out_path else _reports_dir() / _filename("pdf")

    doc = SimpleDocTemplate(
        str(dest),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    W = 17 * cm  # usable width

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=20, textColor=colors.HexColor("#1a2e4a"),
        spaceAfter=4,
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#2c3e50"),
        spaceBefore=14, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=15, textColor=colors.HexColor("#333333"),
    )
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#888888"),
    )
    risk_style = ParagraphStyle(
        "Risk", parent=body_style,
        textColor=colors.HexColor("#c0392b"),
    )
    rec_style = ParagraphStyle(
        "Rec", parent=body_style,
        textColor=colors.HexColor("#117a65"),
    )

    story = []

    # ── Header ────────────────────────────────────────────────────
    story.append(Paragraph(f"{company} — Weekly Business Report", title_style))
    story.append(Paragraph(
        f"Week {kpi_payload.get('week', 'N/A')}  ·  "
        f"Generated: {datetime.now().strftime('%B %d, %Y  %H:%M')}",
        small_style,
    ))
    story.append(HRFlowable(width=W, thickness=2, color=colors.HexColor("#2980b9")))
    story.append(Spacer(1, 0.4 * cm))

    # ── KPI Table ─────────────────────────────────────────────────
    story.append(Paragraph("KPI Snapshot", h2_style))

    kpi_rows = [
        ["Metric", "Value"],
        ["Revenue", kpi_payload.get("revenue", "—")],
        ["Revenue Growth (WoW)", kpi_payload.get("revenue_growth", "—")],
        ["Total Users", kpi_payload.get("users", "—")],
        ["User Growth (WoW)", kpi_payload.get("user_growth", "—")],
        ["Churn Rate", kpi_payload.get("churn_rate", "—")],
        ["Churn Change (WoW)", kpi_payload.get("churn_change", "—")],
        ["Avg Revenue Per User (ARPU)", kpi_payload.get("arpu", "—")],
        ["Retention Rate", kpi_payload.get("retention_rate", "—")],
        ["3-Week Revenue Moving Avg", kpi_payload.get("revenue_ma3", "—")],
        ["Revenue Trend", kpi_payload.get("revenue_trend", "—").capitalize()],
        ["Churn Trend", kpi_payload.get("churn_trend", "—").capitalize()],
    ]
    col_w = [W * 0.60, W * 0.40]
    kpi_table = Table(kpi_rows, colWidths=col_w)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2980b9")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f2f6fc"), colors.white]),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("ALIGN",       (1, 1), (1, -1), "RIGHT"),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#c0cfe0")),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Executive Summary ─────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=colors.HexColor("#bdc3c7")))
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(llm_result.executive_summary, body_style))

    # ── Key Risks ─────────────────────────────────────────────────
    if llm_result.key_risks:
        story.append(Paragraph("Key Risks", h2_style))
        for risk in llm_result.key_risks:
            story.append(Paragraph(f"⚠  {risk}", risk_style))
            story.append(Spacer(1, 0.15 * cm))

    # ── Recommendations ───────────────────────────────────────────
    if llm_result.recommendations:
        story.append(Paragraph("Strategic Recommendations", h2_style))
        for i, rec in enumerate(llm_result.recommendations, 1):
            story.append(Paragraph(f"{i}.  {rec}", rec_style))
            story.append(Spacer(1, 0.15 * cm))

    # ── Anomalies ─────────────────────────────────────────────────
    story.append(Paragraph("Anomaly Detection", h2_style))
    if anomaly_report.has_anomalies:
        anomaly_rows = [["Week", "Metric", "Type", "Description"]]
        for a in anomaly_report.anomalies:
            anomaly_rows.append([
                str(a.week), a.metric.capitalize(),
                a.kind.replace("_", " ").title(), a.description,
            ])
        a_col_w = [W * 0.08, W * 0.12, W * 0.18, W * 0.62]
        a_table = Table(anomaly_rows, colWidths=a_col_w)
        a_table.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#e74c3c")),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fdf2f2"), colors.white]),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#e8c9c9")),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("WORDWRAP",    (3, 1), (3, -1), True),
        ]))
        story.append(a_table)
    else:
        story.append(Paragraph("No statistical anomalies detected in this period.", body_style))

    # ── Outlook ───────────────────────────────────────────────────
    if llm_result.outlook:
        story.append(Spacer(1, 0.3 * cm))
        story.append(HRFlowable(width=W, thickness=0.5, color=colors.HexColor("#bdc3c7")))
        story.append(Paragraph("Outlook", h2_style))
        story.append(Paragraph(llm_result.outlook, body_style))

    # ── Footer ────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor("#2980b9")))
    story.append(Paragraph(
        f"Model: {llm_result.model}  ·  "
        f"Tokens: {llm_result.total_tokens}  ·  "
        f"Latency: {llm_result.latency_seconds}s  ·  "
        f"Cost: ${llm_result.estimated_cost_usd:.6f}",
        small_style,
    ))

    doc.build(story)
    logger.info(f"PDF report saved → {dest}")
    return dest


# ─────────────────────────────────────────────────────────────────
# CSV Report
# ─────────────────────────────────────────────────────────────────

def generate_csv(
    kpi_payload: dict[str, str],
    llm_result: Any,
    anomaly_report: Any,
    full_df: Any | None = None,
    out_path: str | Path | None = None,
) -> Path:
    """
    Generate a structured CSV report.

    Returns the absolute path of the generated file.
    """
    dest = Path(out_path) if out_path else _reports_dir() / _filename("csv")

    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        # ── KPI section ───────────────────────────────────────────
        w.writerow(["SECTION", "WEEKLY KPI SNAPSHOT"])
        w.writerow(["Metric", "Value"])
        for key, val in kpi_payload.items():
            label = key.replace("_", " ").title()
            w.writerow([label, val])

        w.writerow([])

        # ── AI Insights section ───────────────────────────────────
        w.writerow(["SECTION", "AI-GENERATED INSIGHTS"])
        w.writerow(["Executive Summary", llm_result.executive_summary])
        w.writerow([])

        w.writerow(["Key Risks", ""])
        for risk in llm_result.key_risks:
            w.writerow(["", risk])

        w.writerow([])
        w.writerow(["Recommendations", ""])
        for rec in llm_result.recommendations:
            w.writerow(["", rec])

        w.writerow([])
        w.writerow(["Outlook", llm_result.outlook])

        # ── Anomalies section ─────────────────────────────────────
        w.writerow([])
        w.writerow(["SECTION", "ANOMALY DETECTION"])
        if anomaly_report.has_anomalies:
            w.writerow(["Week", "Metric", "Type", "Description"])
            for a in anomaly_report.anomalies:
                w.writerow([a.week, a.metric, a.kind, a.description])
        else:
            w.writerow(["Result", "No anomalies detected"])

        # ── Full week-by-week data ────────────────────────────────
        if full_df is not None:
            w.writerow([])
            w.writerow(["SECTION", "WEEK-BY-WEEK DATA"])
            w.writerow(full_df.columns.tolist())
            for _, row in full_df.iterrows():
                w.writerow(row.tolist())

        # ── Metadata ──────────────────────────────────────────────
        w.writerow([])
        w.writerow(["SECTION", "REPORT METADATA"])
        w.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        w.writerow(["LLM Model", llm_result.model])
        w.writerow(["Total Tokens", llm_result.total_tokens])
        w.writerow(["Latency (s)", llm_result.latency_seconds])

    logger.info(f"CSV report saved → {dest}")
    return dest
