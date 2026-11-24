import re, requests, json
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"}
h = requests.get("https://yjaraviagens.com/", headers=UA, timeout=30).text
main = re.search(r'src="(/assets/main-[^"]+\.js)"', h).group(1)
js = requests.get("https://yjaraviagens.com" + main, headers=UA, timeout=40).text
chave = re.search(r'getAppApiToken\(\)\{return"([^"]+)"', js).group(1)
rotas = re.findall(r'"?([\w.-]+)"?:\((?:\w+(?:=\{\})?,?)*\)=>api\.(get|post)\(`?["\']?([^"\'`,)]+)', js)
print("API:", [(n, m, p) for n, m, p in rotas if m == "get"][:80])
i = js.find("escolher-passagem"); print("ROTA escolher:", js[i-100:i+400])
# testa algumas chamadas
API = "https://app.techrios.online/api"
H = {**UA, "X-API-KEY": chave, "Accept": "application/json", "Origin": "https://yjaraviagens.com", "Referer": "https://yjaraviagens.com/"}
for path, params in [("/municipios", {"subdomain": "yjaraviagens"}), ("/municipios", {}), ("/viagens-em-destaque", {}),
                     ("/trechos-viagem", {"subdomain": "yjaraviagens"})]:
    try:
        r = requests.get(API + path, params=params, headers=H, timeout=30)
        print("GET", path, params, r.status_code, r.text[:500].replace("\n", " "))
    except Exception as e:
        print("ERRO", path, e)
