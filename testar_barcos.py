"""Investiga Terra Santa e escalas (viagem com vários trechos) na Yjara."""
import re, json, requests
from collections import defaultdict
from datetime import date, timedelta
import barcos
H = {**barcos.UA, "X-API-KEY": barcos._chave()}
def get(path, **p):
    r = requests.get(barcos.API + path, params=p, headers=H, timeout=40)
    try: return r.json()
    except Exception: return {"status": r.status_code, "txt": r.text[:200]}
# 1. nome de Terra Santa nos municípios
for p in [{"search": "terra"}, {"nome": "Terra Santa"}, {"q": "terra santa"}, {"uf": "PA"}, {"page": 2}]:
    j = get("/municipios", **p)
    d = j.get("data") if isinstance(j, dict) else None
    lista = d if isinstance(d, list) else (d or {}).get("data", []) if isinstance(d, dict) else []
    achou = [(x.get("slug"), x.get("id")) for x in lista if "terra" in (x.get("slug") or "") or "nhamund" in (x.get("slug") or "") or x.get("slug") in ("faro", "oriximina", "santarem")]
    print("MUN", p, "qtd:", len(lista), "achou:", achou[:8])
dia = (date.today() + timedelta(days=2)).isoformat()
# 2. só origem (todos os destinos)
for o in ["manaus", "santarem", "oriximina", "terra-santa", "trombetas", "faro", "nhamunda"]:
    for extra in [{}, {"data_irrestrita": 1}]:
        j = get("/trechos-viagem", origem=o, destino="", data_hora=dia, quantia=1, subdomain="yjaraviagens", **extra)
        try:
            itens = j["data"]["trechos"]["data"]; tot = j["data"]["trechos"]["total"]
            dest = sorted({x["trecho"] for x in itens})
            print(f"SO-ORIGEM {o:12} {extra} total={tot} trechos={dest[:12]}")
        except Exception:
            print(f"SO-ORIGEM {o:12} {extra} {str(j)[:150]}")
# 3. todos os trechos de uma viagem (escalas): agrupa por id_viagem nas primeiras páginas sem filtro
grupos = defaultdict(set)
for pg in range(1, 8):
    j = get("/trechos-viagem", subdomain="yjaraviagens", page=pg)
    for x in j["data"]["trechos"]["data"]:
        grupos[x["id_viagem"]].add((x["trecho"], x["horario"], x["valor"], x["embarcacao"]))
multi = {k: v for k, v in grupos.items() if len(v) > 1}
print("VIAGENS com vários trechos (amostra):", len(multi), "de", len(grupos))
for k, v in list(multi.items())[:4]:
    print("  VIAGEM", k, sorted(v)[:8])
ts = [(k, v) for k, v in grupos.items() if any("Terra Santa" in t[0] for t in v)]
print("COM TERRA SANTA:", ts[:3])
