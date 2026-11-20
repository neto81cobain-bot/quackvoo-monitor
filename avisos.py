"""Envio dos avisos: e-mail (Gmail) e Telegram."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import re
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
        f"QuackVoo <{u}>",
        para,
    )
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    host = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
    with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as srv:
        srv.login(u, s.replace(" ", ""))
        srv.sendmail(u, [x.strip() for x in para.split(",")], msg.as_string())
    return f"e-mail enviado para {para}"


def _dividir_mensagem(texto: str, limite: int = 3900) -> list[str]:
    if len(texto) <= limite:
        return [texto]

    partes = []
    atual = ""
    for linha in texto.splitlines(keepends=True):
        if len(atual) + len(linha) > limite:
            if atual:
                partes.append(atual)
                atual = ""
            while len(linha) > limite:
                partes.append(linha[:limite])
                linha = linha[limite:]
        atual += linha
    if atual:
        partes.append(atual)
    return partes


def _remover_tags_html(texto: str) -> str:
    sem_link = re.sub(r'<a\s+href=["\'](.*?)["\']>(.*?)</a>', r"\2 (\1)", texto)
    return re.sub(r"<[^>]+>", "", sem_link)


def telegram(texto: str, usar_html: bool = True) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return "telegram: sem TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID, pulei"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    blocos = _dividir_mensagem(texto)

    for bloco in blocos:
        payload = {
            "chat_id": chat_id,
            "text": bloco,
            "disable_web_page_preview": True,
        }
        if usar_html:
            payload["parse_mode"] = "HTML"

        r = requests.post(url, json=payload, timeout=60)

        if not r.ok and usar_html and "can't parse entities" in r.text.lower():
            fallback_payload = {
                "chat_id": chat_id,
                "text": _remover_tags_html(bloco),
                "disable_web_page_preview": True,
            }
            r = requests.post(url, json=fallback_payload, timeout=60)

        if not r.ok:
            return f"telegram falhou ({r.status_code}): {r.text[:120]}"

    return "telegram enviado"


def whatsapp(texto: str) -> str:
    """Mantém compatibilidade caso monitor.py chame avisos.whatsapp(...)."""
    return telegram(texto)
