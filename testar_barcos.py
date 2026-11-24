import re, requests, json
from datetime import date, timedelta
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"}
h = requests.get("https://yjaraviagens.com/", headers=UA, timeout=30).text
js = requests.get("https://yjaraviagens.com" + re.search(r'src="(/assets/main-[^"]+\.js)"', h).group(1), headers=UA, timeout=40).text
chave = re.search(r'getAppApiToken\(\)\{return"([^"]+)"', js).group(1)
c = requests.get("https://yjaraviagens.com/assets/" + re.search(r'import\("\./(ChooseTrip-[^"]+\.js)"\)', js).group(1), headers=UA, timeout=40).text
m = re.search(r"function Y\([^)]*\)\{[^}]{0,300}\}", c) or re.search(r"Y=\([^)]*\)=>[^,;]{0,300}", c)
print("FORMATA DATA:", m.group(0)[:300] if m else "?")
API, H = "https://app.techrios.online/api", {**UA, "X-API-KEY": chave, "Accept": "application/json"}
mun = requests.get(API + "/municipios", headers=H, timeout=30).json()["data"]
ids = {x["slug"]: x["id"] for x in mun}
print("IDS:", {k: ids.get(k) for k in ["oriximina", "santarem", "terra-santa", "obidos", "manaus", "juruti", "faro"]}, "| trombetas:", [x["slug"] for x in mun if "trombet" in x["slug"] or "porto" in x["slug"] and x["uf"] == "PA"][:5])
d = (date.today() + timedelta(days=2)).isoformat()
for o, de in [("oriximina", "santarem"), ("santarem", "oriximina"), ("oriximina", "terra-santa"), ("santarem", "manaus")]:
    for estilo, params in [("slug", {"origem": o, "destino": de}), ("id", {"origem": ids.get(o), "destino": ids.get(de)})]:
        for dh in (d, d + " 00:00:00"):
            p = {**params, "data_hora": dh, "quantia": 1, "subdomain": "yjaraviagens", "intervalo": "", "empresa": "", "tipo_comodidade_id": ""}
            r = requests.get(API + "/trechos-viagem", params=p, headers=H, timeout=30)
            try:
                tr = r.json()["data"]["trechos"]
                itens = tr["data"]
                print(f"{o}->{de} {estilo} '{dh}': total={tr.get('total')} | " + " ; ".join(f"{x['embarcacao']} {x['trecho']} {x['horario']} {x['valor']}" for x in itens[:3]))
            except Exception as e:
                print(f"{o}->{de} {estilo} '{dh}': {r.status_code} {r.text[:150]}")
        break
it = requests.get(API + "/trechos-viagem", params={"subdomain": "yjaraviagens"}, headers=H, timeout=30).json()["data"]["trechos"]["data"][0]
print("CHAVES ITEM:", [k for k in it.keys()])
print("EMPRESA:", {k: it[k] for k in it if "empresa" in k or "operad" in k or "link" in k or "url" in k})
