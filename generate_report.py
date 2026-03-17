#!/usr/bin/env python3
"""
generate_report.py
───────────────────
AI Automated Weekly Reporting System — CLI entry point.

Usage
──────
  python generate_report.py
  python generate_report.py --file data/weekly_data.csv
  python generate_report.py --email founder@company.com
  python generate_report.py --format csv
  python generate_report.py --format both --no-email
  python generate_report.py --file data/weekly_data.csv --email ceo@co.com --format pdf

Flags
──────
  --file   PATH     CSV input file  (default: config.json → data_file)
  --email  ADDRESS  Override recipient(s); comma-separated
  --format          pdf | csv | both  (default: config.json → report_format)
  --no-email        Skip email delivery
  --offline         Skip LLM call; use built-in fallback summary
  --week   N        Target week index from end: 0=latest (default)
"""

import argparse
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate_report.py",
        description="AI Automated Weekly Reporting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file",     default=None, metavar="PATH",
                        help="Path to the weekly CSV data file")
    parser.add_argument("--email",    default=None, metavar="ADDRESS",
                        help="Comma-separated recipient email(s)")
    parser.add_argument("--format",   default=None, choices=["pdf", "csv", "both"],
                        help="Output format: pdf | csv | both")
    parser.add_argument("--no-email", action="store_true",
                        help="Generate report but skip email delivery")
    parser.add_argument("--offline",  action="store_true",
                        help="Skip LLM API; use fallback summary")
    parser.add_argument("--week",     type=int, default=0, metavar="N",
                        help="Week offset from end (0 = latest)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    t_start = time.perf_counter()

    # ── Imports (after arg parse so --help is instant) ────────────
    import pandas as pd
    from src.config import cfg
    from src.logger import get_logger
    from src.kpi_engine import KPIEngine
    from src.anomaly_detection import AnomalyDetector
    from src.report_generator import generate_pdf, generate_csv
    from src.email_sender import EmailSender
    from src.trend_analysis import analyze_3_week_trend
    from src.alert_engine import generate_alerts

    log = get_logger("generate_report")

    # ── 1. Load CSV ───────────────────────────────────────────────
    csv_path = Path(args.file) if args.file else Path(cfg["data_file"])
    if not csv_path.exists():
        print(f"\n[ERROR] Data file not found: {csv_path}")
        print("Tip: create data/weekly_data.csv or pass --file <path>\n")
        return 2

    log.info(f"Loading data from {csv_path}")
    df = pd.read_csv(csv_path)

    # ── 2. KPI Engine ─────────────────────────────────────────────
    log.info("Computing KPIs…")
    engine = KPIEngine(df)
    kpi_result = engine.compute()
    kpi_payload = kpi_result.to_prompt_payload()
    full_df = engine.full_summary_df()
    
    # ── 2b. Trend & Alerts ────────────────────────────────────────
    log.info("Analyzing trends and checking alerts…")
    trend_info = f"3-Week Revenue Trend is {analyze_3_week_trend(df, 'revenue')}."
    alerts = generate_alerts(df, kpi_result)

    # ── 2c. Update History ────────────────────────────────────────
    history_path = Path("data/history.csv")
    history_data = {
         "week": kpi_result.current_week,
         "revenue": kpi_result.revenue,
         "users": kpi_result.users,
         "churn": kpi_result.churn_rate,
         "arpu": kpi_result.arpu,
         "retention": kpi_result.retention_rate
    }
    pd.DataFrame([history_data]).to_csv(history_path, mode='a', header=not history_path.exists(), index=False)

    # ── 3. Anomaly Detection ──────────────────────────────────────
    log.info("Running anomaly detection…")
    detector = AnomalyDetector(df)
    anomaly_report = detector.detect(metrics=["revenue", "users"])

    if anomaly_report.has_anomalies:
        log.warning(f"{len(anomaly_report.anomalies)} anomaly(ies) detected:")
        for line in anomaly_report.summary_lines():
            log.warning(f"  {line}")

    # ── 4. LLM Insight Generation ─────────────────────────────────
    if args.offline:
        log.info("Offline mode — using fallback LLM summary.")
        from src.llm_summary import LLMSummary
        llm_result = LLMSummary._fallback(kpi_payload, "offline mode")
    else:
        log.info("Generating AI insights via Groq…")
        from src.llm_summary import LLMSummary
        llm = LLMSummary()
        llm_result = llm.generate(kpi_payload, anomaly_report.summary_lines())

    # ── 5. Generate Report Files ──────────────────────────────────
    report_format = args.format or cfg.get("report_format", "pdf")
    company = cfg.get("company_name", "My Startup")
    generated_files: list[Path] = []

    if report_format in ("pdf", "both"):
        log.info("Generating PDF report…")
        pdf_path = generate_pdf(
            kpi_payload, llm_result, anomaly_report, 
            company_name=company, alerts=alerts, trend_info=trend_info
        )
        generated_files.append(pdf_path)

    if report_format in ("csv", "both"):
        log.info("Generating CSV report…")
        csv_report_path = generate_csv(
            kpi_payload, llm_result, anomaly_report, 
            full_df=full_df, alerts=alerts, trend_info=trend_info
        )
        generated_files.append(csv_report_path)

    # ── 6. Email Delivery ─────────────────────────────────────────
    email_sent = False
    if not args.no_email:
        recipients = (
            [r.strip() for r in args.email.split(",") if r.strip()]
            if args.email else None
        )
        sender = EmailSender()
        for report_file in generated_files:
            ok = sender.send(
                attachment_path=report_file,
                week=str(kpi_result.current_week),
                kpi_payload=kpi_payload,
                llm_result=llm_result,
                recipients=recipients,
            )
            email_sent = email_sent or ok
    else:
        log.info("Email delivery skipped (--no-email).")

    # ── 7. Summary ────────────────────────────────────────────────
    elapsed = round(time.perf_counter() - t_start, 2)
    divider = "─" * 60
    print(f"\n{divider}")
    print(f"  {company.upper()} — WEEK {kpi_result.current_week} REPORT")
    print(divider)
    print(f"\n{llm_result.executive_summary}\n")
    print("  KPIs:")
    for k, v in kpi_payload.items():
        print(f"    {k:<28} {v}")
    if anomaly_report.has_anomalies:
        print("\n  Anomalies:")
        for line in anomaly_report.summary_lines():
            print(f"    ⚠  {line}")
    if trend_info:
        print(f"\n  Trend Analysis: {trend_info}")
    if alerts:
        print("\n  Business Alerts 🚨:")
        for a in alerts:
            print(f"    • {a}")
    if llm_result.key_risks:
        print("\n  Key Risks:")
        for r in llm_result.key_risks:
            print(f"    • {r}")
    if llm_result.recommendations:
        print("\n  Recommendations:")
        for i, r in enumerate(llm_result.recommendations, 1):
            print(f"    {i}. {r}")
    print(f"\n  Outlook: {llm_result.outlook}")
    print(divider)
    print(f"  Reports saved:")
    for f in generated_files:
        print(f"    → {f}")
    print(f"  Email sent : {'Yes' if email_sent else 'No / skipped'}")
    print(f"  Model      : {llm_result.model}  |  Tokens: {llm_result.total_tokens}")
    print(f"  Total time : {elapsed}s")
    print(divider + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except EnvironmentError as exc:
        print(f"\n[CONFIG ERROR] {exc}")
        print("Copy .env.example → .env and add your GROQ_API_KEY.")
        sys.exit(2)
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        raise
