"""Envio dos avisos: e-mail (Gmail) e Telegram."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib
import ssl
import requests


def email(assunto: str, html: str, texto: str) -> str:
  u, s, para = (
      os.getenv("EMAIL_USER"),
      os.getenv("EMAIL_APP_PASSWORD"),
      os.getenv("EMAIL_TO") or os.getenv("EMAIL_USER"),
  )
  if not (u and s):
    return "e-mail: sem EMAIL_USER/EMAIL_APP_PASSWORD, pulei"
  msg = MIMEMultipart("alternative")
  msg["Subject"], msg["From"], msg["To"] = (
      assunto,
      f"QuackVoo 🦆 <{u}>",
      para,
  )
  msg.attach(MIMEText(texto, "plain", "utf-8"))
  msg.attach(MIMEText(html, "html", "utf-8"))
  host = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
  with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as srv:
    srv.login(u, s.replace(" ", ""))
    srv.sendmail(u, [x.strip() for x in para.split(",")], msg.as_string())
  return f"e-mail enviado para {para}"


def telegram(texto: str) -> str:
  token = os.getenv("TELEGRAM_BOT_TOKEN")
  chat_id = os.getenv("TELEGRAM_CHAT_ID")
  if not (token and chat_id):
    return "telegram: sem TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID, pulei"
  url = f"https://api.telegram.org/bot{token}/sendMessage"
  r = requests.post(
      url,
      json={"chat_id": chat_id, "text": texto[:4000]},
      timeout=60,
  )
  return (
      "telegram enviado"
      if r.ok
      else f"telegram falhou ({r.status_code}): {r.text[:120]}"
  )


def whatsapp(texto: str) -> str:
  """Mantém compatibilidade caso monitor.py chame avisos.whatsapp(...)."""
  return telegram(texto)
