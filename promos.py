"""Promoções postadas por aí: blogs de passagem, portal regional, canais públicos do Telegram e Google Notícias.
Acha as que interessam (seus destinos, saindo do Norte, pacotes, promoção das companhias). Não gasta crédito."""
import html as html_lib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from aeroportos import nome as nome_aero, palavras, sem_acento

# (tipo, endereço). Todas testadas no GitHub Actions em 24/11/2026.
FONTES = {
    "Melhores Destinos": ("rss", "https://www.melhoresdestinos.com.br/feed"),
    "Passageiro de Primeira": ("rss", "https://passageirodeprimeira.com/feed/"),
    "Pontos pra Voar": ("rss", "https://pontospravoar.com/feed/"),
    "Viaje na Viagem": ("rss", "https://www.viajenaviagem.com/feed/"),
    "Portal Amazônia": ("rss", "https://portalamazonia.com/feed/"),
    "Telegram Melhores Destinos": ("tg", "melhoresdestinos"),
    "Telegram Passageiro de Primeira": ("tg", "passageirodeprimeira"),
    "Telegram Cartões e Viagens": ("tg", "canalcartoeseviagens"),
    "Telegram Promobit": ("tg", "promobit"),
}
GNEWS = [  # Google Notícias: só entra o que fala de voo/pacote com preço
    "passagens aéreas promoção Manaus OR Belém OR Santarém when:3d",
    "pacote viagem saindo de Manaus OR Belém OR Santarém when:7d",
    "promoção passagens Latam OR Azul OR Gol when:2d",
]
CABECALHO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
             "Accept": "application/rss+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5", "Accept-Language": "pt-BR,pt;q=0.9"}

AEREO = r"(voos?\b|aere[ao]s?|passage(m|ns) aere|pacotes?\b|trechos?\b|ida e volta|latam|azul\b|\bgol\b|companhias? aere)"
PRECO = r"(r\$\s?\d|a partir de|milhas|% ?off|desconto)"
PACOTE = r"(pacotes?\b|voo \+ hotel|aereo \+ hotel|hospedage|diarias|all inclusive|cruzeiro)"
CIA_PROMO = r"\b(latam|azul|gol)\b.{0,80}(promo|feirao|relampago|a partir de r\$)|(promo|feirao|relampago).{0,80}\b(latam|azul|gol)\b"
MILHAS = r"(milheiro|\bcpm\b|bonus|transferenc|clube (azul|smiles|latam)|livelo|esfera|premmia|pontos\b|cartao|cartoes|assinatura)"
NORTE_EXTRA = ["oriximina", "trombetas", "parintins", "macapa", "boa vista", "porto velho", "rio branco", "altamira", "maraba"]


def _texto(x) -> str:
    t = html_lib.unescape(re.sub(r"<[^>]+>", " ", x or ""))
    return re.sub(r"\s+", " ", t).strip()


def ler_rss(nome: str, url: str) -> list[dict]:
    r = requests.get(url, headers=CABECALHO, timeout=25)
    r.raise_for_status()
    raiz = ET.fromstring(r.content.strip())
    out = []
    for it in raiz.iter("item"):
        titulo = _texto(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        desc = _texto(it.findtext("description"))
        conteudo = ""
        for filho in it:
            if filho.tag.endswith("encoded"):
                conteudo = _texto(filho.text)[:3000]
        quando = None
        try:
            quando = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            pass
        if link:
            out.append({"fonte": nome, "titulo": titulo, "link": link, "texto": f"{titulo} {desc} {conteudo}", "quando": quando})
    return out


def ler_telegram(nome: str, canal: str) -> list[dict]:
    """Prévia pública do canal (t.me/s/canal): não precisa de login."""
    r = requests.get(f"https://t.me/s/{canal}", headers=CABECALHO, timeout=25)
    r.raise_for_status()
    out = []
    for bloco in re.split(r'(?=<div class="tgme_widget_message_wrap)', r.text)[1:]:
        post = re.search(r'data-post="([^"]+)"', bloco)
        corpo = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', bloco, re.S)
        if not (post and corpo):
            continue
        texto = _texto(corpo.group(1).replace("<br/>", "\n").replace("<br>", "\n"))
        quando = None
        d = re.search(r'<time datetime="([^"]+)"', bloco)
        if d:
            try:
                quando = datetime.fromisoformat(d.group(1))
            except ValueError:
                pass
        titulo = re.split(r"(?<=[.!?])\s", texto, maxsplit=1)[0][:140]
        out.append({"fonte": nome, "titulo": titulo, "link": f"https://t.me/{post.group(1)}", "texto": texto, "quando": quando})
    return out


def _acha(palavra: str, texto: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(palavra) + r"(?![a-z])", texto) is not None


def _preco(texto: str) -> str | None:
    m = re.search(r"R\$\s?([\d.]{2,7})", texto)
    return f"R$ {m.group(1)}" if m else None


def combinar(posts: list[dict], rotas: list[dict], extras: list[str], origens: list[str] | None = None) -> list[dict]:
    """Para cada post: por que interessa. ⭐ = fala do seu destino ou de sair do Norte."""
    achados = []
    extras = [sem_acento(x) for x in extras if str(x).strip()]
    norte = {nome_aero(o).split(" (")[0]: palavras(o) for o in (origens or [])}
    for p in posts:
        t = sem_acento(p["texto"])
        titulo = sem_acento(p["titulo"])
        if not re.search(AEREO, t) or not re.search(PRECO, t):
            continue  # não é promoção de viagem (ex.: notícia de barco, de Uber, de pacote fiscal…)
        motivos, estrela = [], False
        for r in rotas:
            alvo = [w for w in palavras(r["destino"]) if _acha(w, t)]
            if alvo:
                no_titulo = any(_acha(w, titulo) for w in alvo)
                motivos.append(f"{r['nome']}" + (" (no título)" if no_titulo else ""))
                estrela = estrela or no_titulo or any(_acha(w, t) for w in palavras(r["origem"]))
        for cidade, ws in norte.items():  # Radar do Norte: post que fala de sair de Manaus, Belém, Santarém…
            if any(re.search(r"(saindo|partindo|saidas?|embarque|origem|de|desde)\s+(de\s+|em\s+)?" + re.escape(w) + r"(?![a-z])", t) for w in ws):
                motivos.append(f"🌴 saindo de {cidade}"); estrela = True
        for w in NORTE_EXTRA:
            if _acha(w, titulo):
                motivos.append(f"🌴 cita {w.title()}"); estrela = True
        for w in extras:
            if _acha(w, t):
                motivos.append(f"palavra “{w}”")
        if re.search(CIA_PROMO, titulo) and not re.search(MILHAS, titulo):  # milhas/pontos não é passagem
            motivos.append("✈️ promoção de companhia")
        if motivos:
            achados.append({**p, "rotas": motivos, "estrela": estrela, "pacote": bool(re.search(PACOTE, titulo)),
                            "preco": _preco(p["titulo"]) or _preco(p["texto"])})
    return achados


def buscar(rotas: list[dict], extras: list[str], fontes: dict | None = None, origens: list[str] | None = None) -> tuple[list[dict], list[str]]:
    posts, erros = [], []
    todas = dict(fontes or FONTES)
    if fontes is None:
        todas["Google Notícias"] = ("multi", ["https://news.google.com/rss/search?q=" + quote(q) + "&hl=pt-BR&gl=BR&ceid=BR:pt-419" for q in GNEWS])
    for nome, (tipo, alvo) in todas.items():
        try:
            if tipo == "rss":
                posts += ler_rss(nome, alvo)
            elif tipo == "tg":
                posts += ler_telegram(nome, alvo)
            elif tipo == "multi":
                for url in alvo:
                    posts += ler_rss(nome, url)
        except Exception as e:
            erros.append(f"{nome}: {str(e)[:80]}")
    agora = datetime.now(timezone.utc)
    posts = [p for p in posts if not p["quando"] or (agora - p["quando"]).days < 4]  # só o que é recente
    return combinar(posts, rotas, extras, origens), erros
