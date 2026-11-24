import re, requests, json
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"}
js = requests.get("https://yjaraviagens.com/assets/main-BOlm1_tx.js", headers=UA, timeout=40).text
for k in ["/trechos-viagem", "/viagens-em-destaque", "/viagens-imbativeis", "app.techrios.online/api", "headers", "cidades", "/cidades"]:
    for m in list(re.finditer(re.escape(k), js))[:2]:
        print(f"[{k}] ...{js[max(0, m.start()-350): m.start()+350]}...\n")
