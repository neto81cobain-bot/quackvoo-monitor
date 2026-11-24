import re, requests, json
from datetime import date, timedelta
import barcos
UA = barcos.UA
h = requests.get("https://navegam.com.br/", headers=UA, timeout=30).text
base, ctx = None, []
for s in re.findall(r'(?:src|href)="(/_next/static/[^"]+\.js)"', h):
    js = requests.get("https://navegam.com.br" + s, headers=UA, timeout=40).text
    for m in re.finditer(r'baseURL', js):
        ctx.append(js[max(0, m.start()-200): m.start()+200])
    for m in re.finditer(r'ecommerce/travels', js):
        ctx.append("TRAVELS: " + js[max(0, m.start()-500): m.start()+200])
    for u in re.findall(r'https://[a-z0-9.-]*navegam[a-z0-9.-]*\.[a-z]{2,4}[a-z0-9/._-]*', js):
        ctx.append("URL " + u)
for c in sorted(set(ctx))[:14]: print("NAVCTX:", c.replace("\n", " ")[:600])
