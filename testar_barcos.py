import re, requests, json
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"}
h = requests.get("https://yjaraviagens.com/", headers=UA, timeout=30).text
main = re.search(r'src="(/assets/main-[^"]+\.js)"', h).group(1)
js = requests.get("https://yjaraviagens.com" + main, headers=UA, timeout=40).text
chave = re.search(r'getAppApiToken\(\)\{return"([^"]+)"', js).group(1)
ct = re.search(r'import\("\./(ChooseTrip-[^"]+\.js)"\)', js).group(1)
c = requests.get("https://yjaraviagens.com/assets/" + ct, headers=UA, timeout=40).text
for m in list(re.finditer(r"trechos-viagem", c))[:3]:
    print("CHAMADA:", c[max(0, m.start()-600): m.start()+300])
API = "https://app.techrios.online/api"
H = {**UA, "X-API-KEY": chave, "Accept": "application/json"}
r = requests.get(API + "/trechos-viagem", params={"subdomain": "yjaraviagens"}, headers=H, timeout=30).json()
t = r["data"]["trechos"]
print("PAGINAÇÃO:", {k: t.get(k) for k in ("current_page", "last_page", "per_page", "total")}, "| outras chaves:", list(r["data"].keys()))
print("ITEM:", json.dumps(t["data"][0], ensure_ascii=False)[:1500])
