"""Teste real dos trechos de barco (não manda nada)."""
import barcos
for o, d in [("oriximina", "santarem"), ("santarem", "oriximina"), ("oriximina", "trombetas"), ("trombetas", "oriximina"),
             ("oriximina", "terra-santa"), ("terra-santa", "oriximina"), ("santarem", "trombetas"), ("santarem", "manaus")]:
    try:
        s = barcos.proximos(o, d, 7)
        n = sum(len(v) for v in s.values())
        ex = next(iter(s.values()))[0] if s else None
        print(f"{o:12}→{d:12} {n:2} saídas em {len(s)} dias" + (f" | ex.: {ex['horario']} {ex['embarcacao']} ({ex['empresa']}) R$ {ex['preco']:.0f} dur={ex['duracao']}" if ex else ""))
    except Exception as e:
        print(o, d, "ERRO", e)
print()
print(barcos.texto("santarem", "oriximina", barcos.proximos("santarem", "oriximina", 3))[:1500])
