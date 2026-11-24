import re, requests, json
from datetime import date, timedelta
import barcos
UA = barcos.UA
B = "https://navegam-fluvial-api-prod-979984919366.us-central1.run.app"
h = requests.get("https://navegam.com.br/", headers=UA, timeout=30).text
caminhos, chamadas = set(), []
for s in re.findall(r'(?:src|href)="(/_next/static/[^"]+\.js)"', h):
    js = requests.get("https://navegam.com.br" + s, headers=UA, timeout=40).text
    caminhos |= set(re.findall(r'["\'`](/?ecommerce/[a-zA-Z_/-]+)', js))
    for m in re.finditer(r'J\(\{|travels",\{params', js):
        chamadas.append(js[max(0, m.start()-300): m.start()+300])
print("NAVPATHS:", sorted(caminhos))
for c in chamadas[:3]: print("NAVCALL:", c.replace("\n", " "))
def g(p, **q):
    r = requests.get(B + p, params=q, headers=UA, timeout=40)
    return r.status_code, r.text[:700].replace("\n", " ")
for p, q in [("/ecommerce/popular-destinations", {"page": 1, "page_size": 50}), ("/ecommerce/popular-itineraries", {}),
             ("/ecommerce/cities", {}), ("/ecommerce/travels", {}), ("/ecommerce/boats", {})]:
    print("NAVGET", p, q, "→", *g(p, **q))
