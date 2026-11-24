import json, os, requests
k = os.getenv("SERPAPI_KEY", "")
e = requests.get("https://serpapi.com/search.json", params={"engine": "google_travel_explore", "departure_id": "MAO", "currency": "BRL", "hl": "pt", "gl": "br", "arrival_area_id": "/m/015fr", "api_key": k}, timeout=60).json()
ds = e.get("destinations") or []
print("explore:", e.get("error"), len(ds), "| chaves topo:", list(e.keys()))
print("params:", json.dumps(e.get("search_parameters"), ensure_ascii=False)[:400])
for x in ds[:3]:
    x.pop("thumbnail", None)
    print("DEST", json.dumps(x, ensure_ascii=False)[:900])
