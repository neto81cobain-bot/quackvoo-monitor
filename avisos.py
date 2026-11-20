"""Envio dos avisos: e-mail (Gmail) e WhatsApp (CallMeBot)."""
import os, smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests


def email(assunto: str, html: str, texto: str) -> str:
    u, s, para = os.getenv("EMAIL_USER"), os.getenv("EMAIL_APP_PASSWORD"), os.getenv("EMAIL_TO") or os.getenv("EMAIL_USER")
    if not (u and s):
        return "e-mail: sem EMAIL_USER/EMAIL_APP_PASSWORD, pulei"
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = assunto, f"QuackVoo 🦆 <{u}>", para
    msg.attach(MIMEText(texto, "plain", "utf-8")); msg.attach(MIMEText(html, "html", "utf-8"))
    host = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
    with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as srv:
        srv.login(u, s.replace(" ", ""))
        srv.sendmail(u, [x.strip() for x in para.split(",")], msg.as_string())
    return f"e-mail enviado para {para}"


def whatsapp(texto: str) -> str:
    fone, chave = os.getenv("WHATSAPP_PHONE"), os.getenv("CALLMEBOT_KEY")
    if not (fone and chave):
        return "whatsapp: sem WHATSAPP_PHONE/CALLMEBOT_KEY, pulei"
    r = requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": fone.replace("+", "").replace(" ", ""), "text": texto[:1500], "apikey": chave}, timeout=60)
    return "whatsapp enviado" if r.ok else f"whatsapp falhou ({r.status_code}): {r.text[:120]}"
