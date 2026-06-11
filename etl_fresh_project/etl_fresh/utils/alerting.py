"""
utils/alerting.py
Slack + Email alerts — pipeline success/failure pe.
Week 4 - Day 4-5
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.logger import get_logger

logger = get_logger("alerting")


class SlackAlerter:
    def __init__(self):
        self.token   = os.getenv("SLACK_BOT_TOKEN", "")
        self.channel = os.getenv("SLACK_CHANNEL", "#etl-alerts")

    def send_success(self, run_id, source, entity, records, duration):
        msg = (
            f"✅ *ETL Success*\n"
            f"> Run: `{run_id}` | Source: *{source}* | Entity: *{entity}*\n"
            f"> Records: *{records:,}* | Time: *{duration:.1f}s*\n"
            f"> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        self._post(msg)

    def send_failure(self, run_id, source, entity, error):
        msg = (
            f"🚨 *ETL FAILED*\n"
            f"> Run: `{run_id}` | Source: *{source}* | Entity: *{entity}*\n"
            f"> Error: ```{str(error)[:300]}```"
        )
        self._post(msg)

    def _post(self, text: str):
        if not self.token or "your" in self.token:
            logger.info(f"[SLACK MOCK] {text[:80]}...")
            return
        try:
            from slack_sdk import WebClient
            WebClient(token=self.token).chat_postMessage(
                channel=self.channel, text=text, mrkdwn=True
            )
        except Exception as e:
            logger.error(f"Slack error: {e}")


class EmailAlerter:
    def __init__(self):
        self.host       = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port       = int(os.getenv("SMTP_PORT", "587"))
        self.user       = os.getenv("SMTP_USER", "")
        self.password   = os.getenv("SMTP_PASSWORD", "")
        self.recipients = os.getenv("ALERT_RECIPIENTS", "").split(",")

    def send_failure(self, run_id, source, error):
        subject = f"[ETL ALERT] Pipeline Failed — {source} — {run_id}"
        body    = (
            f"ETL Pipeline Failure\n"
            f"====================\n"
            f"Run ID : {run_id}\n"
            f"Source : {source}\n"
            f"Time   : {datetime.utcnow().isoformat()} UTC\n\n"
            f"Error:\n{error}"
        )
        if not self.user:
            logger.info(f"[EMAIL MOCK] {subject}")
            return
        try:
            msg              = MIMEMultipart()
            msg["From"]      = self.user
            msg["To"]        = ", ".join(self.recipients)
            msg["Subject"]   = subject
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(self.host, self.port) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.sendmail(self.user, self.recipients, msg.as_string())
        except Exception as e:
            logger.error(f"Email error: {e}")
