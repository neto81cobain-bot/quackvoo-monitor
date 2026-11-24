import requests, barcos
B = barcos.NAVEGAM
base = {"origin_id": 1, "destination_id": 27}
for extra in [{}, {"page": 1}, {"page": 0}, {"page": 2}, {"page_size": 50}, {"limit": 50}, {"per_page": 50}, {"page": 2, "per_page": 10}, {"offset": 10}]:
    j = requests.get(B + "/ecommerce/travels", params={**base, **extra}, headers=barcos.UA, timeout=30).json()
    r = j.get("result") or {}
    dd = r.get("data", []) if isinstance(r, dict) else []
    print("NAVP", extra, "→", len(dd), "total", r.get("total") if isinstance(r, dict) else None, [x["departure_date"][:10] for x in dd][:4], "" if dd else str(j)[:150])
