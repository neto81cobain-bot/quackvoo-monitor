import re, requests, json
from datetime import date, timedelta
import barcos
UA = {**barcos.UA, "Accept": "text/html,application/xhtml+xml"}
b = requests.get("https://navegam.com.br/busca?searchType=boat&type=ida&passageiros=1", headers=UA, timeout=40).text
i = b.find("Terra Santa"); print("BUSCA tem Terra Santa?", i >= 0, "| tam:", len(b))
if i >= 0: print("CTX:", b[max(0, i-400): i+200].replace("\\", ""))
ids = re.findall(r'\\?"id\\?":\s*(\d+),\s*\\?"name\\?":\s*\\?"([^"\\]+)', b)
print("CIDADES (id,nome):", ids[:80])
h = requests.get("https://navegam.com.br/", headers=UA, timeout=30).text
achou = set()
for s in re.findall(r'(?:src|href)="(/_next/static/[^"]+\.js)"', h):
    js = requests.get("https://navegam.com.br" + s, headers=UA, timeout=40).text
    for m in re.finditer(r'(baseURL|NEXT_PUBLIC_[A-Z_]+|fetch\(|\.get\(|\.post\()', js):
        trecho = js[m.start(): m.start()+140]
        if "http" in trecho or '"/' in trecho or "`/" in trecho:
            achou.add(trecho.replace("\n", " "))
for a in sorted(achou)[:30]: print("REQ:", a)
