"""
src/email_sender.py
────────────────────
Email Automation — Gmail SMTP with file attachment.

Sends the generated PDF or CSV as an email attachment via Gmail.
Uses App Password auth (no OAuth required).

Setup
──────
1.  Google Account → Security → 2-Step Verification → enable
2.  https://myaccount.google.com/apppasswords → Mail → copy 16-char code
3.  Set in .env:  EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
4.  Set sender + recipients in config.json

Features
─────────
• HTML + plain text multipart body
• File attachment (any type; auto-detects MIME type)
• Validation before attempting SMTP connection
• Clear error messages for common auth failures
"""

import mimetypes
import os
import smtplib
import ssl
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from src.config import cfg, ROOT
from src.logger import get_logger

logger = get_logger(__name__)


class EmailSender:
    """Composes and sends the weekly report email with an attachment."""

    def __init__(self) -> None:
        self._email_cfg: dict = cfg.get("email", {})
        self._company: str = cfg.get("company_name", "My Startup")

    # ── Public ────────────────────────────────────────────────────

    def send(
        self,
        attachment_path: Path,
        week: str,
        kpi_payload: dict[str, str],
        llm_result: Any,
        recipients: list[str] | None = None,
    ) -> bool:
        """
        Send the report email with the given file attached.

        Parameters
        ──────────
        attachment_path : Path to the PDF or CSV file
        week            : Week label, e.g. "10"
        kpi_payload     : dict from KPIResult.to_prompt_payload()
        llm_result      : LLMResult instance
        recipients      : Override the config.json recipient list

        Returns True on success, False on failure.
        """
        sender: str = self._email_cfg.get("sender", "")
        password: str = self._email_cfg.get("app_password", "").replace(" ", "")

        # Always reload .env so values updated after server start are picked up
        load_dotenv(ROOT / ".env", override=True)
        sender   = os.getenv("EMAIL_SENDER",       sender).strip()
        password = os.getenv("EMAIL_APP_PASSWORD", password).replace(" ", "")
        to_list: list[str] = recipients or self._email_cfg.get("recipients", [])
        cc_list: list[str] = self._email_cfg.get("cc", [])

        if not sender or not password:
            logger.error(
                "Email not sent: EMAIL_SENDER or EMAIL_APP_PASSWORD is missing. "
                "Add them to .env or pass --no-email to skip."
            )
            return False

        if not to_list:
            logger.error("Email not sent: no recipients configured.")
            return False

        if not attachment_path.exists():
            logger.error(f"Email not sent: attachment not found at {attachment_path}")
            return False

        subject = (
            f"[{self._company}] Weekly Business Report — "
            f"Week {week} — {datetime.now().strftime('%b %d, %Y')}"
        )

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{self._company} Reports <{sender}>"
        msg["To"] = ", ".join(to_list)
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)

        # Body (HTML + plain fallback)
        body_alt = MIMEMultipart("alternative")
        body_alt.attach(MIMEText(self._plain_body(week, kpi_payload, llm_result), "plain", "utf-8"))
        body_alt.attach(MIMEText(self._html_body(week, kpi_payload, llm_result), "html", "utf-8"))
        msg.attach(body_alt)

        # Attachment
        self._attach_file(msg, attachment_path)

        all_recipients = to_list + cc_list
        smtp_host: str = self._email_cfg.get("smtp_host", "smtp.gmail.com")
        smtp_port: int = int(self._email_cfg.get("smtp_port", 465))

        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as server:
                server.login(sender, password)
                server.sendmail(sender, all_recipients, msg.as_string())
            logger.info(f"Email sent → {all_recipients}  attachment={attachment_path.name}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error(
                "Gmail authentication failed. "
                "Use a 16-character App Password, not your Gmail login password. "
                "Generate one at https://myaccount.google.com/apppasswords"
            )
        except smtplib.SMTPException as exc:
            logger.error(f"SMTP error: {exc}")
        except Exception as exc:
            logger.error(f"Unexpected email error: {exc}")
        return False

    # ── Private ───────────────────────────────────────────────────

    @staticmethod
    def _attach_file(msg: MIMEMultipart, path: Path) -> None:
        mime_type, _ = mimetypes.guess_type(str(path))
        main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            data = f.read()
        part = MIMEBase(main_type, sub_type)
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)

    def _html_body(self, week: str, kpi: dict[str, str], llm: Any) -> str:
        risks_html = "".join(f"<li>{r}</li>" for r in llm.key_risks)
        recs_html = "".join(f"<li>{r}</li>" for r in llm.recommendations)
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;color:#222;background:#f5f7fa;margin:0;padding:20px}}
  .card{{background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);
         max-width:660px;margin:0 auto;padding:32px}}
  h1{{font-size:20px;color:#1a2e4a;border-bottom:3px solid #2980b9;padding-bottom:8px}}
  h2{{font-size:14px;color:#2c3e50;margin-top:22px}}
  p{{line-height:1.7;font-size:13px}}
  table{{width:100%;border-collapse:collapse;margin-top:8px}}
  td{{padding:7px 10px;border-bottom:1px solid #eee;font-size:12px}}
  td:first-child{{color:#555;width:55%}}td:last-child{{font-weight:bold}}
  ul{{margin:6px 0 0 18px;padding:0;font-size:12px;line-height:1.8}}
  .risk li{{color:#c0392b}}.rec li{{color:#117a65}}
  .footer{{font-size:10px;color:#aaa;margin-top:24px;border-top:1px solid #eee;padding-top:10px}}
</style></head><body><div class="card">
<h1>📊 {self._company} — Weekly Report (Week {week})</h1>
<h2>Executive Summary</h2><p>{llm.executive_summary}</p>
<h2>KPI Snapshot</h2>
<table>
  <tr><td>Revenue</td><td>{kpi.get('revenue','—')}</td></tr>
  <tr><td>Revenue Growth</td><td>{kpi.get('revenue_growth','—')}</td></tr>
  <tr><td>Users</td><td>{kpi.get('users','—')}</td></tr>
  <tr><td>User Growth</td><td>{kpi.get('user_growth','—')}</td></tr>
  <tr><td>Churn Rate</td><td>{kpi.get('churn_rate','—')}</td></tr>
  <tr><td>ARPU</td><td>{kpi.get('arpu','—')}</td></tr>
  <tr><td>Retention Rate</td><td>{kpi.get('retention_rate','—')}</td></tr>
</table>
<h2>Key Risks</h2><ul class="risk">{risks_html}</ul>
<h2>Recommendations</h2><ul class="rec">{recs_html}</ul>
<p><em>{llm.outlook}</em></p>
<div class="footer">
  Model: {llm.model} · Tokens: {llm.total_tokens} ·
  Latency: {llm.latency_seconds}s · Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
</div></div></body></html>"""

    def _plain_body(self, week: str, kpi: dict[str, str], llm: Any) -> str:
        risks = "\n".join(f"  • {r}" for r in llm.key_risks)
        recs = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(llm.recommendations))
        return f"""{self._company} — Weekly Report (Week {week})
{"=" * 55}

EXECUTIVE SUMMARY
{llm.executive_summary}

KPI SNAPSHOT
  Revenue          : {kpi.get('revenue', '—')}
  Revenue Growth   : {kpi.get('revenue_growth', '—')}
  Users            : {kpi.get('users', '—')}
  User Growth      : {kpi.get('user_growth', '—')}
  Churn Rate       : {kpi.get('churn_rate', '—')}
  ARPU             : {kpi.get('arpu', '—')}
  Retention Rate   : {kpi.get('retention_rate', '—')}

KEY RISKS
{risks}

RECOMMENDATIONS
{recs}

OUTLOOK
{llm.outlook}

{"=" * 55}
Model: {llm.model} | Tokens: {llm.total_tokens} | Latency: {llm.latency_seconds}s
"""
