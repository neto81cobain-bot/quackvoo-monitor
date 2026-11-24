"""Teste real: ofertas oficiais + promoções (não manda nada)."""
import yaml, ofertas, promos, radar, fontes
cfg = yaml.safe_load(open("rotas.yaml"))
rotas = [r for r in cfg["rotas"] if r.get("ativa") is not False]
lista, erros = ofertas.coletar()
print("OFICIAIS lidas:", len(lista), "erros:", erros)
est = {}
dest = {}
for r in rotas: dest.setdefault(r["destino"], set()).update([r["origem"], *(r.get("conexoes") or [])])
ofertas.avaliar(est, lista, radar.ORIGENS_PADRAO, dest, "2026-11-24T10:00:00+00:00")
boas = ofertas.avaliar(est, lista, radar.ORIGENS_PADRAO, dest, "2026-11-24T12:00:00+00:00")
print("OFICIAIS do Norte/destino:", len(est["oficiais"]["ultimas"]), "| avisaria agora:", len(boas))
for o in sorted(est["oficiais"]["ultimas"].values(), key=lambda o: o["preco"])[:15]:
    print("  OF", o["cia"], o["nome_o"], "→", o["nome_d"], o["preco"], o["ida"], o["volta"] or "só ida")
ach, err = promos.buscar(rotas, [], origens=radar.ORIGENS_PADRAO)
print("PROMOS achadas:", len(ach), "erros:", err)
for p in ach[:12]:
    print("  PR", "⭐" if p["estrela"] else "  ", "📦" if p["pacote"] else "  ", p["fonte"][:20], "|", p["titulo"][:80], "|", ", ".join(p["rotas"])[:50])
