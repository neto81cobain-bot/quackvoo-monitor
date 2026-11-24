"""Promoções dos blogs de passagem (Melhores Destinos, Passagens Imperdíveis...): lê o RSS e acha as que
falam dos seus destinos. Não gasta crédito nenhum."""
import html as html_lib
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

from aeroportos import palavras, sem_acento

FEEDS = {
    "Melhores Destinos": "https://www.melhoresdestinos.com.br/feed",
    "Passagens Imperdíveis": "https://www.passagensimperdiveis.com.br/feed/",
    "Passageiro de Primeira": "https://passageirodeprimeira.com/feed/",
}
CABECALHO = {"User-Agent": "Mozilla/5.0 (QuackVoo Monitor; +https://github.com)"}


def _texto(x) -> str:
    t = html_lib.unescape(re.sub(r"<[^>]+>", " ", x or ""))
    return re.sub(r"\s+", " ", t).strip()


def ler_feed(nome: str, url: str) -> list[dict]:
    r = requests.get(url, headers=CABECALHO, timeout=25)
    r.raise_for_status()
    raiz = ET.fromstring(r.content)
    out = []
    for it in raiz.iter("item"):
        titulo = _texto(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        desc = _texto(it.findtext("description"))
        conteudo = ""
        for filho in it:
            if filho.tag.endswith("encoded"):
                conteudo = _texto(filho.text)
        quando = None
        try:
            quando = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            pass
        if link:
            out.append({"fonte": nome, "titulo": titulo, "link": link, "texto": f"{titulo} {desc} {conteudo}", "quando": quando})
    return out


def _acha(palavra: str, texto: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(palavra) + r"(?![a-z])", texto) is not None


def _preco(texto: str) -> str | None:
    m = re.search(r"R\$\s?([\d.]{2,7})", texto)
    return f"R$ {m.group(1)}" if m else None


def combinar(posts: list[dict], rotas: list[dict], extras: list[str]) -> list[dict]:
    """Para cada post: quais rotas ele interessa. Destino no texto = relevante; origem também = ⭐."""
    achados = []
    extras = [sem_acento(x) for x in extras if str(x).strip()]
    for p in posts:
        t = sem_acento(p["texto"])
        titulo = sem_acento(p["titulo"])
        motivos, estrela = [], False
        for r in rotas:
            alvo = [w for w in palavras(r["destino"]) if _acha(w, t)]
            if alvo:
                origem = any(_acha(w, t) for w in palavras(r["origem"]))
                no_titulo = any(_acha(w, titulo) for w in alvo)
                motivos.append(f"{r['nome']}" + (" (no título)" if no_titulo else ""))
                estrela = estrela or origem or no_titulo
        for w in extras:
            if _acha(w, t):
                motivos.append(f"palavra “{w}”")
        if motivos:
            achados.append({**p, "rotas": motivos, "estrela": estrela, "preco": _preco(p["titulo"]) or _preco(p["texto"])})
    return achados


def buscar(rotas: list[dict], extras: list[str], feeds: dict | None = None) -> tuple[list[dict], list[str]]:
    posts, erros = [], []
    for nome, url in (feeds or FEEDS).items():
        try:
            posts += ler_feed(nome, url)
        except Exception as e:
            erros.append(f"{nome}: {str(e)[:80]}")
    return combinar(posts, rotas, extras), erros
