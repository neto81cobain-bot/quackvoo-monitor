"""Testa páginas oficiais de ofertas e mais feeds de notícia de turismo."""
import re, html, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
def limpa(t): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
for url in ["https://passagens.voeazul.com.br/pt/melhores-ofertas", "https://passagens.voeazul.com.br/pt/ofertas-azul",
            "https://passagens.voeazul.com.br/pt/ofertas-imperdiveis", "https://passagens.voeazul.com.br/pt/ofertas/manaus",
            "https://passagens.voeazul.com.br/pt/ofertas-de-manaus", "https://www.azulviagens.com.br/ofertas",
            "https://www.voegol.com.br/ofertas", "https://www.voegol.com.br/promocoes", "https://b2c.voegol.com.br/ofertas",
            "https://www.decolar.com/ofertas-viagens/gol", "https://www.decolar.com/ofertas-viagens/azul",
            "https://www.latamairlines.com/br/pt/ofertas-voos"]:
    try:
        r = requests.get(url, headers=UA, timeout=25)
        t = limpa(r.text)
        precos = re.findall(r"R\$ ?[\d.]+,\d{2}", t)
        rotas = re.findall(r"([A-ZÀ-Úa-zà-ú .]+ \([A-Z]{3}\)) ?Para ?([A-ZÀ-Úa-zà-ú .]+ \([A-Z]{3}\))", t)
        norte = [x for x in rotas if re.search(r"\((MAO|BEL|STM|TMT)\)", " ".join(x))]
        print(f"{r.status_code} {url[:60]:60} tam={len(r.text)} preços={len(precos)} rotas={len(rotas)} norte={len(norte)} {rotas[:2]} {norte[:3]}")
    except Exception as e:
        print("ERRO", url, str(e)[:80])
for nome, url in {"Mercado & Eventos": "https://www.mercadoeeventos.com.br/feed/", "Catraca Livre viagem": "https://catracalivre.com.br/viagem-livre/feed/",
                  "Panrotas": "https://www.panrotas.com.br/feed/", "Aeroin": "https://aeroin.net/feed/", "Aeroflap": "https://www.aeroflap.com.br/feed/",
                  "Brasilturis": "https://brasilturis.com.br/feed/", "Mundo Viagem": "https://www.mundoviagem.com.br/feed/",
                  "Portal Amazônia": "https://portalamazonia.com/feed/", "D24AM": "https://d24am.com/feed/", "O Liberal": "https://www.oliberal.com/rss",
                  "A Crítica": "https://www.acritica.com/rss", "G1 AM": "https://g1.globo.com/rss/g1/am/amazonas/", "G1 PA": "https://g1.globo.com/rss/g1/pa/para/"}.items():
    try:
        r = requests.get(url, headers=UA, timeout=25)
        itens = re.findall(r"<item>.*?<title>(.*?)</title>", r.text, re.S)
        print(f"RSS {r.status_code} {nome:22} itens={len(itens)} | {' || '.join(html.unescape(re.sub(r'<!\\[CDATA\\[|\\]\\]>', '', x)).strip()[:55] for x in itens[:2])}")
    except Exception as e:
        print("RSS ERRO", nome, str(e)[:80])
