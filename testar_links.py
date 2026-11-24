"""Confere se os links das agências/companhias abrem e se o 'onde comprar' do Google funciona."""
import os, re, sys
import requests
import fontes, inteligencia as I

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9"}
o, d, dia = (sys.argv[1:4] + ["MAO", "VVI", "2027-05-29"][len(sys.argv[1:4]):])
for grupo, lista in I.links_sites(o, d, dia).items():
    for nome, url, _ in lista:
        try:
            r = requests.get(url, headers=UA, timeout=25, allow_redirects=True)
            t = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
            print(f"{grupo:10} {nome:16} {r.status_code} {r.url[:90]} | {(t.group(1).strip()[:60] if t else '')}")
        except Exception as e:
            print(f"{grupo:10} {nome:16} ERRO {str(e)[:90]}")
chave = os.getenv("SERPAPI_KEY")
v = fontes.detalhes_voo(o, d, dia, 1, chave)
print("\nvoo:", {k: v.get(k) for k in ("preco", "cia", "saida")} if v else None, "| token:", bool(v and v.get("booking_token")))
ops = fontes.onde_comprar(o, d, dia, 1, chave, v and v.get("booking_token"))
for x in ops[:8]:
    print(f"  {x['vendedor']:28} {x['preco']}  {x['url'][:80]}")
for x in ops[:3]:
    try:
        r = requests.get(x["url"], headers=UA, timeout=25, allow_redirects=False)
        print(f"  GET {x['vendedor']}: {r.status_code} → {r.headers.get('location', '')[:110]}")
    except Exception as e:
        print("  GET erro", e)
