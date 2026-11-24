"""Navegam: descobre a API; Yjara: tenta buscar uma viagem pelo id (pra mostrar as paradas)."""
import re, json, requests
from datetime import date, timedelta
import barcos
UA = barcos.UA
h = requests.get("https://navegam.com.br/", headers=UA, timeout=30).text
print("NAV título:", re.search(r"<title>(.*?)</title>", h, re.S).group(1)[:80] if "<title>" in h else "?")
srcs = re.findall(r'src="([^"]+\.js[^"]*)"', h)
print("NAV scripts:", srcs[:8])
links = sorted(set(re.findall(r'href="(https?://[^"]+)"', h)))
print("NAV links:", [l for l in links if "navegam" in l or "app" in l][:15])
for s in srcs[:5]:
    u = s if s.startswith("http") else "https://navegam.com.br" + ("" if s.startswith("/") else "/") + s
    try: js = requests.get(u, headers=UA, timeout=40).text
    except Exception as e: print("ERRO", u, e); continue
    apis = sorted(set(re.findall(r'https?://[a-zA-Z0-9.-]*(?:api|navegam)[a-zA-Z0-9./_-]*', js)))[:15]
    caminhos = sorted(set(re.findall(r'["\'`](/[a-z_-]*(?:viage|trecho|passage|busca|rota|linha|porto|cidade|municipio|embarca)[a-z_/-]*)["\'`]', js)))[:20]
    if apis or caminhos: print("NAV", u[-40:], "| apis:", apis, "| caminhos:", caminhos)
# Yjara: id_viagem como filtro?
H = {**UA, "X-API-KEY": barcos._chave()}
dia = (date.today() + timedelta(days=1)).isoformat()
j = requests.get(barcos.API + "/trechos-viagem", params={"origem": "oriximina", "destino": "trombetas", "data_hora": dia, "subdomain": "yjaraviagens", "quantia": 1}, headers=H, timeout=30).json()
it = j["data"]["trechos"]["data"]
if it:
    vid = it[0]["id_viagem"]
    for p in [{"id_viagem": vid}, {"viagem": vid}, {"viagem_id": vid}]:
        r = requests.get(barcos.API + "/trechos-viagem", params={**p, "subdomain": "yjaraviagens"}, headers=H, timeout=30).json()
        tt = sorted({x["trecho"] for x in r["data"]["trechos"]["data"] if x["id_viagem"] == vid})
        print("YJ filtro", p, "→ trechos da viagem:", tt, "| total retornado:", r["data"]["trechos"]["total"])
    print("YJ porto/linhas:", {k: it[0].get(k) for k in ("porto_origem", "linhas", "tempo_viagem", "vantagens")})
