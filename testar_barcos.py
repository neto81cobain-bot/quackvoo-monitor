"""Teste real: /barco com as duas plataformas e paradas (não manda nada)."""
import barcos
for o, d in [("santarem", "oriximina"), ("oriximina", "trombetas"), ("manaus", "oriximina"), ("manaus", "parintins"), ("manaus", "terra-santa")]:
    s = barcos.proximos(o, d, 4, paradas=True)
    n = sum(len(v) for v in s.values()); fontes = {x.get("fonte", "Yjara") for vs in s.values() for x in vs}
    print(f"BARCO {o}→{d}: {n} saídas, fontes={fontes}, com paradas={sum(1 for vs in s.values() for x in vs if x.get('via'))}")
print(barcos.texto("manaus", "oriximina", barcos.proximos("manaus", "oriximina", 4, paradas=True))[:1400])
