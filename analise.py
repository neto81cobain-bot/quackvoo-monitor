"""Análises: melhor dia, melhor período, dia da semana, mês e conexões por conta própria."""
from datetime import date, timedelta

SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def d(s): return date.fromisoformat(s)
def mais(s, n): return (d(s) + timedelta(days=n)).isoformat()
def br(s): return d(s).strftime("%d/%m") + f" ({SEMANA[d(s).weekday()]})"
def reais(n): return "R$ " + f"{round(n):,}".replace(",", ".")


def melhor_dia(cal: dict) -> tuple[str, dict] | None:
    return min(cal.items(), key=lambda kv: kv[1]["preco"]) if cal else None


def melhor_periodo(cal: dict, tamanho=7) -> dict | None:
    """Semana (7 dias seguidos) com a menor média: bom pra quem tem datas flexíveis."""
    dias = sorted(cal)
    melhor = None
    for i, ini in enumerate(dias):
        janela = [cal[x]["preco"] for x in dias[i:] if (d(x) - d(ini)).days < tamanho]
        if len(janela) < max(3, tamanho - 2):
            continue
        media = sum(janela) / len(janela)
        if not melhor or media < melhor["media"]:
            melhor = {"inicio": ini, "fim": mais(ini, tamanho - 1), "media": media}
    return melhor


def por_dia_semana(cal: dict) -> list[tuple[str, float]]:
    soma, n = [0] * 7, [0] * 7
    for k, v in cal.items():
        w = d(k).weekday(); soma[w] += v["preco"]; n[w] += 1
    return [(SEMANA[i], soma[i] / n[i]) for i in range(7) if n[i]]


def por_mes(cal: dict) -> list[dict]:
    m: dict[str, list] = {}
    for k, v in cal.items():
        m.setdefault(k[:7], []).append((k, v["preco"]))
    out = []
    for mes, itens in sorted(m.items()):
        dia_min = min(itens, key=lambda x: x[1])
        out.append({"mes": f"{MESES[int(mes[5:]) - 1]}/{mes[2:4]}", "menor": dia_min[1], "dia": dia_min[0],
                    "media": sum(p for _, p in itens) / len(itens)})
    return out


def combinar_conexao(perna1: dict, perna2: dict, dias_conexao=(0, 1)) -> dict:
    """Para cada data de saída: perna1(dia) + perna2(dia ou dia+1), o mais barato.
    Retorna {data_saida: {total, p1, p2, data2}}."""
    out = {}
    for dia1, a in perna1.items():
        opcoes = [(mais(dia1, k), perna2[mais(dia1, k)]) for k in dias_conexao if mais(dia1, k) in perna2]
        if not opcoes:
            continue
        dia2, b = min(opcoes, key=lambda x: x[1]["preco"])
        out[dia1] = {"total": a["preco"] + b["preco"], "p1": a, "p2": b, "data2": dia2}
    return out
