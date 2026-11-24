"""Teste real: /barco com as duas plataformas e paradas (não manda nada)."""
import barcos
for o, d in [("manaus", "parintins"), ("parintins", "manaus"), ("manaus", "terra-santa"), ("manaus", "faro"), ("santarem", "oriximina")]:
    s = barcos.proximos(o, d, 5, paradas=True)
    fontes = {}
    for vs in s.values():
        for x in vs: fontes[x.get("fonte", "Yjara")] = fontes.get(x.get("fonte", "Yjara"), 0) + 1
    print(f"BARCO {o}→{d}: {fontes}")
print(barcos.texto("manaus", "parintins", barcos.proximos("manaus", "parintins", 2, paradas=True))[:1600])
