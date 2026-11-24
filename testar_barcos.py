import re, json, requests
from datetime import date, timedelta
import barcos
UA = barcos.UA
h = requests.get("https://navegam.com.br/", headers=UA, timeout=30).text
srcs = re.findall(r'(?:src|href)="(/_next/static/[^"]+\.js)"', h)
print("NAV qtd scripts:", len(srcs))
achou = {}
for s in srcs:
    try: js = requests.get("https://navegam.com.br" + s, headers=UA, timeout=40).text
    except Exception: continue
    for u in set(re.findall(r'https?://[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._/-]*)?', js)):
        if any(k in u for k in ("api", "navegam", "backend", "server")) and "github" not in u and "w3.org" not in u:
            achou.setdefault(u, s[-30:])
    for c in set(re.findall(r'["\'`](/(?:api|v1|v2)?/?[a-z_-]*(?:viage|trecho|passage|busca|rota|linha|porto|cidade|municipio|embarca|search|trip|route)[a-zA-Z_/${}.-]*)["\'`]', js)):
        achou.setdefault("CAMINHO " + c, s[-30:])
for k, v in sorted(achou.items())[:40]: print("NAV", k, "←", v)
# Yjara: filtro por id_viagem
H = {**UA, "X-API-KEY": barcos._chave()}
for i in range(1, 4):
    dia = (date.today() + timedelta(days=i)).isoformat()
    it = requests.get(barcos.API + "/trechos-viagem", params={"origem": "santarem", "destino": "manaus", "data_hora": dia, "subdomain": "yjaraviagens", "quantia": 1}, headers=H, timeout=30).json()["data"]["trechos"]["data"]
    if it: break
vid = it[0]["id_viagem"]; print("YJ viagem", vid, it[0]["embarcacao"])
for p in [{"id_viagem": vid}, {"viagem": vid}, {"viagem_id": vid}]:
    r = requests.get(barcos.API + "/trechos-viagem", params={**p, "subdomain": "yjaraviagens"}, headers=H, timeout=30).json()
    tt = sorted({x["trecho"] for x in r["data"]["trechos"]["data"] if x["id_viagem"] == vid})
    print("YJ filtro", p, "→", tt, "| total:", r["data"]["trechos"]["total"])
print("YJ campos:", {k: it[0].get(k) for k in ("porto_origem", "linhas", "tempo_viagem")})
