import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib import parse, request

MAX_TELEGRAM_CHARS = 4096


def _dividir_mensagem(texto: str, limite: int = MAX_TELEGRAM_CHARS) -> list[str]:
    if len(texto) <= limite:
        return [texto]

    partes: list[str] = []
    atual = ""
    for linha in texto.splitlines(keepends=True):
        if len(linha) > limite:
            if atual:
                partes.append(atual.rstrip("\n"))
                atual = ""
            for i in range(0, len(linha), limite):
                partes.append(linha[i : i + limite])
            continue

        if len(atual) + len(linha) > limite:
            partes.append(atual.rstrip("\n"))
            atual = linha
        else:
            atual += linha

    if atual.strip():
        partes.append(atual.rstrip("\n"))
    return partes


def telegram(mensagem: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Faltam os segredos TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    partes = _dividir_mensagem(mensagem)

    for idx, parte in enumerate(partes, 1):
        payload = parse.urlencode(
            {
                "chat_id": chat_id,
                "text": parte,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        req = request.Request(url, data=payload, method="POST")
        with request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Telegram retornou HTTP {resp.status} na parte {idx}/{len(partes)}.")

    return f"Telegram enviado com sucesso ({len(partes)} parte(s))."


def whatsapp(mensagem: str) -> str:
    return telegram(mensagem)


def email(assunto: str, html: str, texto: str) -> str:
    usuario = os.getenv("EMAIL_USER", "").strip()
    senha = os.getenv("EMAIL_APP_PASSWORD", "").strip()
    destino = os.getenv("EMAIL_TO", "").strip()
    if not usuario or not senha or not destino:
        return "E-mail ignorado (segredos EMAIL_USER/EMAIL_APP_PASSWORD/EMAIL_TO não configurados)."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = usuario
    msg["To"] = destino
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
        smtp.login(usuario, senha)
        smtp.sendmail(usuario, [destino], msg.as_string())

    return f"E-mail enviado para {destino}."
