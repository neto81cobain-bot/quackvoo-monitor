"""Descobre a API que o site da Yjara usa por trás."""
import re, requests
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"}
base = "https://yjaraviagens.com"
h = requests.get(base + "/escolher-passagem/oriximina/santarem/somente-ida/2026-11-28", headers=UA, timeout=30).text
print("HTML:", h[:1500].replace("\n", " "))
srcs = re.findall(r'src="([^"]+\.js[^"]*)"', h)
print("SCRIPTS:", srcs)
for s in srcs[:6]:
    u = s if s.startswith("http") else base + ("" if s.startswith("/") else "/") + s
    try:
        js = requests.get(u, headers=UA, timeout=40).text
    except Exception as e:
        print("ERRO", u, e); continue
    print(f"--- {u} ({len(js)} bytes)")
    for pad in [r'https?://[a-zA-Z0-9.-]*(?:api|techrios|yjara)[a-zA-Z0-9./_-]*', r'baseURL\s*[:=]\s*["\'][^"\']+', r'["\'](/api/[^"\']{2,80})["\']',
                r'["\']([a-z_/-]*(?:viage|trecho|passage|pesquis|busca|cidade|linha|horario)[a-z_/{}$.-]{0,60})["\']']:
        achados = sorted(set(re.findall(pad, js)))[:30]
        if achados: print("  ", pad[:30], "→", achados)
