"""Compara Apify x Fli na mesma rota (python comparar_fontes.py MAO VVI 2027-05-25 2027-09-05 [noites])."""
import os, sys, time
import fontes

o, d, ini, fim = sys.argv[1:5]
n = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].isdigit() else None
t = time.time(); fli = fontes.calendario_fli(o, d, ini, fim, 1, n); tf = time.time() - t
print(f"Fli: {len(fli)} dias em {tf:.0f}s")
ap = {}
if os.getenv("APIFY_TOKEN") and "--sem-apify" not in sys.argv:
    t = time.time(); ap = fontes.calendario_apify(o, d, ini, fim, 1, n, os.environ["APIFY_TOKEN"]); print(f"Apify: {len(ap)} dias em {time.time() - t:.0f}s")
if fli:
    k = min(fli, key=lambda x: fli[x]["preco"]); print(f"Fli mais barato: R$ {fli[k]['preco']} em {k}")
if ap:
    k = min(ap, key=lambda x: ap[x]["preco"]); print(f"Apify mais barato: R$ {ap[k]['preco']} em {k}")
    comuns = sorted(set(ap) & set(fli))
    iguais = sum(1 for x in comuns if abs(ap[x]["preco"] - fli[x]["preco"]) <= max(5, ap[x]["preco"] * 0.01))
    print(f"Dias em comum: {len(comuns)} · praticamente iguais (±1%): {iguais}")
    difs = sorted(comuns, key=lambda x: -abs(ap[x]["preco"] - fli[x]["preco"]))[:5]
    for x in difs: print(f"  {x}: Apify {ap[x]['preco']} · Fli {fli[x]['preco']}")
