"""Testa leitura de passagens de barco/lancha (Yjara e outras)."""
import re, html, requests
from datetime import date, timedelta
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
def limpa(t): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
d = (date.today() + timedelta(days=3)).isoformat()
for o, de in [("oriximina", "santarem"), ("santarem", "oriximina"), ("oriximina", "trombetas"), ("trombetas", "oriximina"),
              ("oriximina", "terra-santa"), ("terra-santa", "oriximina"), ("santarem", "trombetas"), ("santarem", "manaus")]:
    url = f"https://yjaraviagens.com/escolher-passagem/{o}/{de}/somente-ida/{d}"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        t = limpa(r.text)
        precos = re.findall(r"R\$ ?[\d.]+,\d{2} no PIX", t)
        barcos = re.findall(r"((?:LANCHA|NAVIO|N/M|B/M|FERRY|EXPRESSO|BARCO)[A-ZÀ-Ú0-9 .'-]{2,40}?) Operado por: ([A-ZÀ-Ú0-9 .&'-]{2,40}?) Saída", t)
        print(f"{r.status_code} {o}->{de} {d} tam={len(r.text)} preços={len(precos)} barcos={len(set(barcos))} {sorted(set(barcos))[:3]}")
        if precos and o == "oriximina" and de == "santarem":
            i = t.find("Operado por"); print("   CTX:", t[max(0, i-250): i+450])
        if not precos:
            j = t.find("Nenhum"); print("   msg:", t[j:j+120] if j >= 0 else t[:200])
    except Exception as e:
        print("ERRO", url, str(e)[:80])
for url in ["https://lanchastapajos.yjaraviagens.com/", "https://yjaraviagens.com/", "https://navegam.com.br/", "https://www.navegam.com.br/",
            "https://uba.app.br/", "https://embarco.app/"]:
    try:
        r = requests.get(url, headers=UA, timeout=25)
        t = limpa(r.text)
        rotas = re.findall(r"([A-ZÀ-Úa-zà-ú ]+/(?:PA|AM|AP)) ([A-ZÀ-Úa-zà-ú ]+/(?:PA|AM|AP)) R\$ ?([\d.]+,\d{2})", t)
        print(f"{r.status_code} {url:42} tam={len(r.text)} rotas={len(rotas)} {rotas[:4]}")
    except Exception as e:
        print("ERRO", url, str(e)[:80])
