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


# ---------------------------------------------------------------- relatório como imagem
def html_para_png(html: str, largura: int = 420) -> bytes:
    """Desenha o HTML do relatório (o mesmo do e-mail) numa imagem PNG nítida."""
    from playwright.sync_api import sync_playwright

    pagina = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>body{margin:0;background:#fff;padding:14px 12px 8px;"
        "font-family:Arial,'Liberation Sans','Noto Color Emoji',sans-serif}</style></head>"
        f"<body>{html}</body></html>"
    )
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": largura, "height": 800}, device_scale_factor=2)
        pg.set_content(pagina, wait_until="load")
        png = pg.screenshot(full_page=True)
        nav.close()
    return png


def telegram_foto(png: bytes, legenda: str, botoes: list[list[tuple[str, str]]], silencioso: bool = False) -> str:
    """Manda a imagem com legenda e botões de link (imagem não tem link clicável)."""
    import json, uuid

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Faltam os segredos TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID.")

    teclado = {"inline_keyboard": [[{"text": t, "url": u} for t, u in linha] for linha in botoes if linha]}
    campos = {"chat_id": chat_id, "caption": legenda[:1024], "parse_mode": "HTML", "reply_markup": json.dumps(teclado),
              "disable_notification": "true" if silencioso else "false"}
    fronteira = uuid.uuid4().hex
    corpo = b""
    for k, v in campos.items():
        corpo += f"--{fronteira}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    corpo += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"quackvoo.png\"\r\n"
              "Content-Type: image/png\r\n\r\n").encode() + png + f"\r\n--{fronteira}--\r\n".encode()
    req = request.Request(f"https://api.telegram.org/bot{token}/sendPhoto", data=corpo, method="POST",
                          headers={"Content-Type": f"multipart/form-data; boundary={fronteira}"})
    with request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Telegram retornou HTTP {resp.status} ao enviar a imagem.")
    return "Telegram: imagem enviada."


# ---------------------------------------------------------------- Telegram: chamadas genéricas (vigia e comandos)
def tg(metodo: str, dados: dict | None = None, timeout: int = 30) -> dict:
    import json
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta o segredo TELEGRAM_BOT_TOKEN.")
    corpo = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in (dados or {}).items() if v is not None}
    req = request.Request(f"https://api.telegram.org/bot{token}/{metodo}", data=parse.urlencode(corpo).encode(), method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:  # HTTPError traz o motivo no corpo
        corpo_erro = getattr(e, "read", lambda: b"")()
        raise RuntimeError(f"Telegram {metodo}: {e} {corpo_erro[:200]!r}")


def teclado(botoes: list[list[tuple[str, str]]] | None) -> dict | None:
    if not botoes:
        return None
    # link (http…) vira botão de abrir; o resto ("/comando", "m", "b|…") é botão de ação (callback)
    return {"inline_keyboard": [[({"text": t, "url": u} if u.startswith(("http://", "https://", "tg://")) else {"text": t, "callback_data": u[:64]}) for t, u in linha]
                                 for linha in botoes if linha]}


def tamanho_visivel(html_txt: str) -> int:
    import html, re
    return len(html.unescape(re.sub(r"<[^>]+>", "", html_txt)).encode("utf-16-le")) // 2


def mensagem(texto: str, botoes=None, silencioso: bool = False, chat_id: str | None = None) -> dict:
    """Mensagem HTML com botões de link. Textos longos são divididos (botões vão na última parte)."""
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
    # o limite do Telegram (4096) conta o texto visível, sem as tags e os endereços dos links
    partes = [texto] if tamanho_visivel(texto) <= MAX_TELEGRAM_CHARS else _dividir_mensagem(texto)
    r = {}
    for i, parte in enumerate(partes):
        r = tg("sendMessage", {"chat_id": chat, "text": parte, "parse_mode": "HTML", "disable_web_page_preview": "true",
                               "disable_notification": "true" if silencioso else "false",
                               "reply_markup": teclado(botoes) if i == len(partes) - 1 else None})
    return r


def foto_url(url: str, legenda: str, botoes=None, silencioso: bool = False, chat_id: str | None = None) -> dict:
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return tg("sendPhoto", {"chat_id": chat, "photo": url, "caption": legenda[:1024], "parse_mode": "HTML",
                            "disable_notification": "true" if silencioso else "false", "reply_markup": teclado(botoes)}, timeout=60)


def hora_silenciosa(agora=None) -> bool:
    """Entre 22h e 7h (Brasília) as mensagens chegam sem som (menos promoção forte)."""
    from datetime import datetime, timedelta, timezone
    agora = agora or datetime.now(timezone(timedelta(hours=-3)))
    return agora.hour >= 22 or agora.hour < 7
