import re, requests, html as H
import barcos
UA = barcos.UA
h = requests.get("https://navegam.com.br/", headers=UA, timeout=30).text
s = [x for x in re.findall(r'(?:src|href)="(/_next/static/[^"]+\.js)"', h) if "7536" in x][0]
js = requests.get("https://navegam.com.br" + s, headers=UA, timeout=40).text
for m in list(re.finditer(r"/busca", js))[:3]:
    print("NAVJS:", js[max(0, m.start()-700): m.start()+300].replace("\n", " "))
t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h)))
print("NAVHOME:", t[:1200])
cid = sorted(set(re.findall(r'"(?:slug|nome|name|label|value)"\s*:\s*"([^"]{3,40})"', h)))[:60]
print("NAVCIDADES:", cid)
