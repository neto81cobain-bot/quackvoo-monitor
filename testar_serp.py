"""Diagnóstico da SerpAPI: cota, google_flights e google_travel_explore."""
import json, os, requests
k = os.getenv("SERPAPI_KEY", "")
print("chave presente:", bool(k))
a = requests.get("https://serpapi.com/account.json", params={"api_key": k}, timeout=30).json()
print("conta:", {x: a.get(x) for x in ("plan_name", "searches_per_month", "plan_searches_left", "total_searches_left", "this_month_usage", "error")})
p = {"engine": "google_flights", "departure_id": "MAO", "arrival_id": "VVI", "outbound_date": "2027-05-29", "type": 2,
     "adults": 1, "currency": "BRL", "hl": "pt", "gl": "br", "api_key": k}
d = requests.get("https://serpapi.com/search.json", params=p, timeout=60).json()
print("flights:", d.get("error"), len(d.get("best_flights") or []), len(d.get("other_flights") or []), list(d.keys())[:8])
v = (d.get("best_flights") or d.get("other_flights") or [{}])[0]
print("  1º voo:", v.get("price"), "token:", bool(v.get("booking_token")))
if v.get("booking_token"):
    b = requests.get("https://serpapi.com/search.json", params={**p, "booking_token": v["booking_token"]}, timeout=60).json()
    for o in (b.get("booking_options") or [])[:6]:
        t = o.get("together") or o
        req = t.get("booking_request") or {}
        print("  vende:", t.get("book_with"), t.get("price"), req.get("url"), (req.get("post_data") or "")[:60])
    print("  google_flights_url:", (b.get("search_metadata") or {}).get("google_flights_url", "")[:100])
e = requests.get("https://serpapi.com/search.json", params={"engine": "google_travel_explore", "departure_id": "MAO", "currency": "BRL",
                 "hl": "pt", "gl": "br", "api_key": k}, timeout=60).json()
print("explore:", e.get("error"), list(e.keys())[:10])
for x in (e.get("destinations") or [])[:5]:
    print("  ", json.dumps(x, ensure_ascii=False)[:300])
