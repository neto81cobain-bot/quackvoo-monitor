"""Diagnóstico: variações da Explorar (SerpAPI) e se o link de compra redireciona."""
import json, os, requests
k = os.getenv("SERPAPI_KEY", "")
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"}
for extra in [{"departure_id": "BEL", "hl": "pt", "gl": "br"}, {"departure_id": "MAO", "hl": "en", "gl": "us"},
              {"departure_id": "MAO", "hl": "pt-BR", "gl": "br", "type": "2"}, {"departure_id": "MAO", "arrival_area_id": "/m/015fr", "hl": "pt", "gl": "br"}]:
    e = requests.get("https://serpapi.com/search.json", params={"engine": "google_travel_explore", "currency": "BRL", "api_key": k, **extra}, timeout=60).json()
    ds = e.get("destinations") or []
    print("explore", extra, "→", e.get("error"), len(ds))
    for x in ds[:2]: print("   ", json.dumps(x, ensure_ascii=False)[:260])
p = {"engine": "google_flights", "departure_id": "MAO", "arrival_id": "VVI", "outbound_date": "2027-05-29", "type": 2,
     "adults": 1, "currency": "BRL", "hl": "pt", "gl": "br", "api_key": k}
d = requests.get("https://serpapi.com/search.json", params=p, timeout=60).json()
v = (d.get("best_flights") or [{}])[0]
b = requests.get("https://serpapi.com/search.json", params={**p, "booking_token": v.get("booking_token")}, timeout=60).json()
for o in (b.get("booking_options") or [])[:2]:
    t = o.get("together") or o; req = t.get("booking_request") or {}
    url = req["url"] + "?" + req["post_data"]
    r = requests.get(url, headers=UA, timeout=25, allow_redirects=False)
    print("GET", t.get("book_with"), r.status_code, r.headers.get("location", "")[:120])
    r2 = requests.post(req["url"], data=req["post_data"], headers={**UA, "Content-Type": "application/x-www-form-urlencoded"}, timeout=25, allow_redirects=False)
    print("POST", t.get("book_with"), r2.status_code, r2.headers.get("location", "")[:120])
