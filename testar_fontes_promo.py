"""Mostra o que o vigia acharia agora nas fontes de promoção (não manda nada)."""
import yaml, promos, radar
cfg = yaml.safe_load(open("rotas.yaml"))
achados, erros = promos.buscar([r for r in cfg["rotas"] if r.get("ativa") is not False], [], origens=radar.ORIGENS_PADRAO)
print("erros:", erros)
print("achados:", len(achados))
for p in sorted(achados, key=lambda x: not x["estrela"])[:25]:
    print(f"{'⭐' if p['estrela'] else '  '}{'📦' if p['pacote'] else '  '} [{p['fonte'][:24]}] {p['titulo'][:90]} | {', '.join(p['rotas'])[:60]}")
