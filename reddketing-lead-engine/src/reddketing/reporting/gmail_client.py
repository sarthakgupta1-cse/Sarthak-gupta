"""Email delivery: Gmail API (gmail.send scope only) or Gmail SMTP with an App Password."""
from __future__ import annotations

import base64
import logging
import smtplib
import ssl
from email.message import EmailMessage

from ..config import env
from ..utils.http import backoff_sleep

logger = logging.getLogger(__name__)
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class EmailError(Exception):
    pass


def build_message(sender: str, recipient: str, subject: str, html: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"Reddketing Lead Engine <{sender}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


class GmailApiSender:
    URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    def __init__(self):
        self.client_id = env("GMAIL_CLIENT_ID")
        self.client_secret = env("GMAIL_CLIENT_SECRET")
        self.refresh_token = env("GMAIL_REFRESH_TOKEN")
        self.sender = env("GMAIL_SENDER")
        if not all([self.client_id, self.client_secret, self.refresh_token, self.sender]):
            raise EmailError("Gmail API needs GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_SENDER")

    def _session(self):
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import AuthorizedSession, Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(None, refresh_token=self.refresh_token, client_id=self.client_id,
                            client_secret=self.client_secret, token_uri="https://oauth2.googleapis.com/token",
                            scopes=[GMAIL_SEND_SCOPE])
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise EmailError("Gmail OAuth refresh failed — the refresh token was revoked or expired. "
                             "Re-run scripts/get_gmail_refresh_token.py and update the GMAIL_REFRESH_TOKEN secret. "
                             f"({exc.__class__.__name__})") from exc
        return AuthorizedSession(creds)

    def send(self, recipient: str, subject: str, html: str, text: str) -> str:
        msg = build_message(self.sender, recipient, subject, html, text)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        session = self._session()
        last = ""
        for attempt in range(3):
            resp = session.post(self.URL, json={"raw": raw}, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("id", "")
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in (429, 500, 502, 503):
                backoff_sleep(attempt, base=3)
                continue
            break
        raise EmailError(f"Gmail API send failed: {last}")


class SmtpSender:
    def __init__(self):
        self.user = env("SMTP_USERNAME") or env("GMAIL_SENDER")
        self.password = env("SMTP_APP_PASSWORD")
        if not self.user or not self.password:
            raise EmailError("SMTP needs SMTP_USERNAME (or GMAIL_SENDER) and SMTP_APP_PASSWORD")

    def send(self, recipient: str, subject: str, html: str, text: str) -> str:
        msg = build_message(self.user, recipient, subject, html, text)
        last = ""
        for attempt in range(3):
            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=60) as s:
                    s.login(self.user, self.password)
                    s.send_message(msg)
                return msg.get("Message-ID", "") or "smtp-sent"
            except smtplib.SMTPAuthenticationError as exc:
                raise EmailError("SMTP authentication failed — check the Gmail App Password") from exc
            except (smtplib.SMTPException, OSError) as exc:
                last = str(exc)
                backoff_sleep(attempt, base=3)
        raise EmailError(f"SMTP send failed: {last}")


def email_transport() -> str:
    """EMAIL_TRANSPORT if set; otherwise SMTP when only an App Password is configured, else the Gmail API."""
    chosen = env("EMAIL_TRANSPORT")
    if chosen:
        return chosen.lower()
    return "smtp" if env("SMTP_APP_PASSWORD") and not env("GMAIL_REFRESH_TOKEN") else "gmail_api"


def build_sender():
    return SmtpSender() if email_transport() == "smtp" else GmailApiSender()
