"""Wysyłka raportów na Gmail (SMTP smtp.gmail.com:587, STARTTLS, hasło aplikacji z GitHub Secrets)."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class MailConfigError(RuntimeError):
    pass


def send_mail(subject: str, html: str, text: str | None = None) -> None:
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("MAIL_TO") or user
    if not user or not password:
        raise MailConfigError("Brak GMAIL_USER / GMAIL_APP_PASSWORD w zmiennych środowiskowych (GitHub Secrets).")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(text or "Raport w wersji HTML.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as s:
        s.starttls()
        s.login(user, password.replace(" ", ""))
        s.send_message(msg)
