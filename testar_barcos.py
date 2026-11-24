import requests, barcos
from datetime import date
B = barcos.NAVEGAM
cid = barcos._cidades_navegam()
print("NAVIDS:", cid.get("manaus"), cid.get("parintins"), len(cid))
datas = []
for pg in range(1, 6):
    j = requests.get(B + "/ecommerce/travels", params={"origin_id": cid["manaus"], "destination_id": cid["parintins"], "page": pg, "page_size": 50}, headers=barcos.UA, timeout=30).json()
    dd = (j.get("result") or {}).get("data", [])
    datas += [x["departure_date"][:10] for x in dd]
    print("NAVPG", pg, len(dd), (j.get("result") or {}).get("total"))
    if len(dd) < 10: break
print("NAVDATAS:", sorted(set(datas))[:20])
r = barcos.navegam("manaus", "parintins", date.today(), 14)
print("NAVRES:", {k: len(v) for k, v in r.items()})
