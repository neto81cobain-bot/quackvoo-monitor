import requests, json
from datetime import date, timedelta
import barcos
B, UA = "https://navegam-fluvial-api-prod-979984919366.us-central1.run.app", barcos.UA
c = requests.get(B + "/ecommerce/popular-destinations", params={"page": 1, "page_size": 100}, headers=UA, timeout=40).json()["result"]["data"]
print("NAVCID:", [(x["id"], x["name"], x["state"]) for x in c])
ids = {x["name"]: x["id"] for x in c}
alvo = [n for n in ids if any(k in n for k in ("Terra Santa", "Faro", "Nhamund", "Oriximin", "Santar", "Juruti", "Óbidos", "Parintins"))]
print("NAVALVO:", [(n, ids[n]) for n in alvo])
o, d = ids.get("Manaus"), ids.get("Parintins")
dia = (date.today() + timedelta(days=2)).isoformat()
for q in [{"origin_city_id": o, "destination_city_id": d}, {"origin": o, "destination": d}, {"originCityId": o, "destinationCityId": d},
          {"origin_id": o, "destination_id": d}, {"origem": o, "destino": d}]:
    for extra in [{}, {"departure_date": dia}, {"date": dia}]:
        try:
            r = requests.get(B + "/ecommerce/travels", params={**q, **extra}, headers=UA, timeout=40).json()
            dd = r["result"]["data"]
            print("NAVFILTRO", q, extra, "→", len(dd), sorted({(x["origin"]["name"], x["destination"]["name"]) for x in dd})[:4], "| total:", r["result"].get("total"))
        except Exception as e:
            print("NAVFILTRO", q, extra, "ERRO", str(e)[:100])
x = requests.get(B + "/ecommerce/travels", headers=UA, timeout=40).json()["result"]
print("NAVCHAVES:", list(x.keys()), "| item:", list(x["data"][0].keys()))
print("NAVITEM:", json.dumps({k: x["data"][0][k] for k in x["data"][0] if k not in ("cost_per_age",)}, ensure_ascii=False)[:1200])
