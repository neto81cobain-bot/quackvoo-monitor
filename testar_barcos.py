import requests
import barcos
B, UA = "https://navegam-fluvial-api-prod-979984919366.us-central1.run.app", barcos.UA
c = []
for pg in (1, 2, 3):
    j = requests.get(B + "/ecommerce/popular-destinations", params={"page": pg, "page_size": 50}, headers=UA, timeout=40).json()
    c += (j.get("result") or {}).get("data", [])
ids = {x["name"].strip(): x["id"] for x in c}
print("NAVTEM:", {k: ids.get(k) for k in ["Manaus", "Terra Santa", "Oriximiná", "Santarém", "Faro", "Nhamundá", "Juruti", "Óbidos", "Parintins"]})
def viagens(o, d):
    out = []
    for pg in range(1, 6):
        j = requests.get(B + "/ecommerce/travels", params={"origin_id": o, "destination_id": d, "page": pg, "page_size": 50}, headers=UA, timeout=40).json()
        dd = (j.get("result") or {}).get("data", [])
        out += dd
        if len(dd) < 10: break
    return out
for a, b in [("Manaus", "Terra Santa"), ("Terra Santa", "Manaus"), ("Santarém", "Terra Santa"), ("Terra Santa", "Santarém"),
             ("Terra Santa", "Oriximiná"), ("Oriximiná", "Terra Santa"), ("Manaus", "Oriximiná"), ("Manaus", "Santarém"), ("Parintins", "Terra Santa")]:
    if a not in ids or b not in ids:
        print(f"NAVTRECHO {a}→{b}: cidade não cadastrada"); continue
    v = viagens(ids[a], ids[b])
    ex = v[0] if v else None
    print(f"NAVTRECHO {a}→{b}: {len(v)} viagens" + (f" | {ex['departure_date'][:16]} {ex['boat']['name']} R$ {ex['transportation_cost']} (+comida {ex['feeding_cost']}) chega {ex['arrival_date'][:16]}" if ex else ""))
