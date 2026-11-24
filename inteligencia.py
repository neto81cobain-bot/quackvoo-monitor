"""O 'olho de quem entende': esse preço é bom? compro já ou espero? + gráficos, feriados e links."""
from datetime import date, timedelta
from statistics import median

import analise as A


# ---------------------------------------------------------------- preço típico e tendência
def tipico(cal: dict, h: dict, google: dict | None = None) -> tuple[float | None, str]:
    """Preço 'normal' da rota. Prioridade: faixa típica do Google > mediana do calendário > histórico."""
    if google and google.get("faixa"):
        lo, hi = google["faixa"]
        return (lo + hi) / 2, f"faixa típica do Google ({A.reais(lo)}–{A.reais(hi)})"
    if cal and len(cal) >= 7:
        return median(v["preco"] for v in cal.values()), "preço mais comum nas suas datas"
    serie = [e["melhor"] for e in h.get("execucoes", [])]
    if len(serie) >= 3:
        return median(serie), "seu histórico"
    return None, ""


def tendencia(h: dict, preco_atual: float | None = None) -> tuple[str, float]:
    """Compara o preço de agora com a média das últimas buscas (até 6)."""
    serie = [e["melhor"] for e in h.get("execucoes", [])][-6:]
    if preco_atual is not None:
        serie = serie + [preco_atual]
    if len(serie) < 3:
        return "pouco histórico", 0.0
    antes = sum(serie[:-1]) / len(serie[:-1])
    var = serie[-1] / antes - 1
    if var <= -0.04: return "caindo", var
    if var >= 0.04: return "subindo", var
    return "estável", var


def veredito(preco: float, cal: dict, h: dict, r: dict, google: dict | None = None) -> dict:
    """Nível do preço + conselho prático (compre / espere)."""
    tip, fonte_tip = tipico(cal, h, google)
    desconto = (1 - preco / tip) if tip else 0.0
    rec = h.get("recorde", {}).get("preco")
    eh_recorde = bool(rec and preco <= rec)
    tend, var = tendencia(h, preco)
    ini = A.d(str(r["ida_entre"][0]))
    faltam = (max(ini, date.today()) - date.today()).days

    if desconto >= 0.25 or (google and google.get("nivel") == "low" and desconto >= 0.15):
        nivel, emoji, rotulo = "promo", "🔥", "Promoção forte"
    elif desconto >= 0.12 or (eh_recorde and desconto >= 0.05):
        nivel, emoji, rotulo = "bom", "✅", "Preço bom"
    elif desconto > -0.10:
        nivel, emoji, rotulo = "normal", "😐", "Preço normal"
    else:
        nivel, emoji, rotulo = "caro", "💸", "Preço alto"

    alvo = r.get("preco_alvo")
    if nivel == "promo":
        conselho = "Compre agora: preço assim costuma sumir em horas."
    elif nivel == "bom" and (tend == "subindo" or faltam <= 60):
        conselho = "Compre: está bom e " + ("começou a subir." if tend == "subindo" else "a viagem está chegando.")
    elif nivel == "bom":
        conselho = "Bom pra comprar. Se quiser arriscar esperar, eu continuo vigiando."
    elif nivel == "normal" and faltam > 90:
        conselho = "Pode esperar: ainda falta bastante e o preço está na média."
    elif nivel == "normal":
        conselho = "Está na média e a viagem se aproxima: " + (f"se não cair até perto de {A.reais(alvo)}, compre." if alvo else "não espere muito.")
    else:
        conselho = "Espere: está acima do normal pra essas datas."

    detalhes = []
    if tip:
        detalhes.append(f"{abs(round(desconto * 100))}% {'abaixo' if desconto >= 0 else 'acima'} do normal ({A.reais(tip)}, {fonte_tip})")
    if google and google.get("nivel"):
        detalhes.append("Google classifica como preço " + {"low": "BAIXO", "typical": "típico", "high": "ALTO"}.get(google["nivel"], google["nivel"]))
    if tend != "pouco histórico":
        detalhes.append(f"tendência: {tend}" + (f" ({var * 100:+.0f}%)" if tend != "estável" else ""))
    if eh_recorde and rec:
        detalhes.append("o menor preço que já vi nessa rota")
    if faltam:
        detalhes.append(f"faltam {faltam} dias pro início do período")
    return {"nivel": nivel, "emoji": emoji, "rotulo": rotulo, "conselho": conselho, "detalhes": detalhes,
            "desconto": desconto, "tipico": tip, "tendencia": tend}


def forte(motivos: list[str], v: dict | None) -> bool:
    """Merece notificação com som? Promoção forte, recorde, alvo ou rede de segurança pós-compra."""
    if v and v.get("nivel") == "promo":
        return True
    return any(m.startswith(("🏆", "🎯", "🛟", "🔥")) for m in motivos)


# ---------------------------------------------------------------- feriados nacionais
def _pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def feriados(ano: int) -> dict[str, str]:
    p = _pascoa(ano)
    fixos = {(1, 1): "Ano Novo", (4, 21): "Tiradentes", (5, 1): "Dia do Trabalho", (9, 7): "Independência",
             (10, 12): "N. Sra. Aparecida", (11, 2): "Finados", (11, 15): "Proclamação da República",
             (11, 20): "Consciência Negra", (12, 25): "Natal"}
    out = {date(ano, m, d).isoformat(): n for (m, d), n in fixos.items()}
    out[(p - timedelta(days=48)).isoformat()] = "Carnaval"
    out[(p - timedelta(days=47)).isoformat()] = "Carnaval"
    out[(p - timedelta(days=2)).isoformat()] = "Sexta-feira Santa"
    out[(p + timedelta(days=60)).isoformat()] = "Corpus Christi"
    return out


def feriados_no_periodo(ini: str, fim: str) -> list[tuple[str, str]]:
    todos = {}
    for ano in range(A.d(ini).year, A.d(fim).year + 1):
        todos.update(feriados(ano))
    return sorted((k, v) for k, v in todos.items() if ini <= k <= fim)


def etiqueta_feriado(dia: str, lista: list[tuple[str, str]]) -> str:
    """'🎉 véspera de Corpus Christi' se o dia é feriado ou até 2 dias antes de um."""
    for k, nome in lista:
        dif = (A.d(k) - A.d(dia)).days
        if dif == 0: return f"🎉 {nome}"
        if 0 < dif <= 2: return f"🎉 véspera de {nome}"
    return ""


# ---------------------------------------------------------------- links para comparar
def links_comparar(o: str, dst: str, dia: str, noites: int, adultos: int) -> list[tuple[str, str]]:
    d1 = A.d(dia)
    volta = d1 + timedelta(days=noites) if noites else None
    sky = f"https://www.skyscanner.com.br/transporte/passagens-aereas/{o.lower()}/{dst.lower()}/{d1:%y%m%d}/" + (f"{volta:%y%m%d}/" if volta else "") + f"?adultsv2={adultos}&rtn={1 if volta else 0}"
    kay = f"https://www.kayak.com.br/flights/{o}-{dst}/{d1.isoformat()}" + (f"/{volta.isoformat()}" if volta else "") + (f"/{adultos}adults" if adultos > 1 else "") + "?sort=price_a"
    return [("Skyscanner", sky), ("Kayak", kay)]


# ---------------------------------------------------------------- gráficos (SVG no relatório)
def svg_evolucao(h: dict, preco_atual: float | None = None, largura=356, altura=110) -> str:
    """Linha do menor preço a cada busca."""
    pts = [(e["t"], e["melhor"]) for e in h.get("execucoes", [])][-40:]
    if preco_atual is not None and (not pts or pts[-1][1] != preco_atual):
        pts.append((date.today().isoformat(), preco_atual))
    if len(pts) < 2:
        return ""
    vals = [p for _, p in pts]
    lo, hi = min(vals), max(vals)
    if hi == lo: hi = lo + 1
    m_esq, m_dir, m_top, m_bai = 6, 6, 18, 20
    W, H = largura - m_esq - m_dir, altura - m_top - m_bai
    xy = [(m_esq + i * W / (len(pts) - 1), m_top + (1 - (p - lo) / (hi - lo)) * H) for i, (_, p) in enumerate(pts)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"{m_esq},{m_top + H} " + linha + f" {m_esq + W},{m_top + H}"
    ix = vals.index(lo)
    xl, yl = xy[ix]
    return (f"<svg width='{largura}' height='{altura}' viewBox='0 0 {largura} {altura}' xmlns='http://www.w3.org/2000/svg' style='display:block'>"
            f"<polygon points='{area}' fill='#DCFCE7'/><polyline points='{linha}' fill='none' stroke='#16A34A' stroke-width='2.5' stroke-linejoin='round'/>"
            f"<circle cx='{xy[-1][0]:.1f}' cy='{xy[-1][1]:.1f}' r='4' fill='#16A34A'/>"
            f"<circle cx='{xl:.1f}' cy='{yl:.1f}' r='3.5' fill='#fff' stroke='#16A34A' stroke-width='2'/>"
            f"<text x='{m_esq}' y='12' font-size='11' fill='#6b7280' font-family='Arial'>máx {A.reais(hi)}</text>"
            f"<text x='{largura - m_dir}' y='12' font-size='11' fill='#6b7280' text-anchor='end' font-family='Arial'>agora {A.reais(vals[-1])} · mín {A.reais(lo)}</text>"
            f"<text x='{m_esq}' y='{altura - 4}' font-size='11' fill='#9ca3af' font-family='Arial'>{A.d(pts[0][0]).strftime('%d/%m')}</text>"
            f"<text x='{largura - m_dir}' y='{altura - 4}' font-size='11' fill='#9ca3af' text-anchor='end' font-family='Arial'>hoje</text></svg>")


def _cor(p: float, lo: float, hi: float) -> str:
    t = 0 if hi == lo else (p - lo) / (hi - lo)
    paleta = ["#15803D", "#22C55E", "#86EFAC", "#FDE68A", "#FDBA74", "#F87171"]
    return paleta[min(int(t * len(paleta)), len(paleta) - 1)]


def html_calor(cal: dict, fer: list[tuple[str, str]] | None = None, max_meses=6) -> str:
    """Calendário colorido: verde = barato, vermelho = caro. Um bloquinho por mês."""
    if not cal:
        return ""
    precos = sorted(v["preco"] for v in cal.values())
    lo, hi = precos[0], precos[int(len(precos) * 0.9) - 1] if len(precos) > 5 else precos[-1]
    feriados_set = {k for k, _ in (fer or [])}
    meses = sorted({k[:7] for k in cal})[:max_meses]
    blocos = []
    for mes in meses:
        a, m = int(mes[:4]), int(mes[5:])
        prim = date(a, m, 1)
        cel = ["<td></td>"] * prim.weekday()
        x = prim
        while x.month == m:
            k = x.isoformat()
            if k in cal:
                p = cal[k]["preco"]
                borda = "outline:2px solid #2563EB;" if k in feriados_set else ""
                cel.append(f"<td title='{A.reais(p)}' style='background:{_cor(min(p, hi), lo, hi)};{borda}color:#111;border-radius:4px;text-align:center;font-size:9px;height:16px;padding:0'>{x.day}</td>")
            else:
                cel.append(f"<td style='color:#d1d5db;text-align:center;font-size:9px;padding:0'>{x.day}</td>")
            x += timedelta(days=1)
        linhas = "".join("<tr>" + "".join(cel[i:i + 7]) + "</tr>" for i in range(0, len(cel), 7))
        blocos.append(f"<div style='display:inline-block;vertical-align:top;width:172px;margin:0 4px 6px 0'>"
                      f"<div style='font-size:12px;font-weight:700;margin-bottom:2px'>{A.MESES[m - 1]}/{str(a)[2:]}</div>"
                      f"<table style='border-collapse:separate;border-spacing:1px;width:100%'><tr style='color:#9ca3af;font-size:9px;text-align:center'>"
                      + "".join(f"<td>{s[0].upper()}</td>" for s in A.SEMANA) + f"</tr>{linhas}</table></div>")
    legenda = (f"<div style='font-size:11px;color:#6b7280'>🟩 {A.reais(lo)} … 🟥 {A.reais(hi)}+"
               + (" · contorno azul = feriado" if feriados_set & set(cal) else "") + "</div>")
    return "<div style='margin-top:10px'><b>Calendário de preços</b><div style='margin-top:4px'>" + "".join(blocos) + "</div>" + legenda + "</div>"


def texto_calor(cal: dict, mes: str | None = None) -> str:
    """Versão em texto (Telegram) do calendário: 🟩🟨🟥 por dia."""
    if not cal:
        return "Sem preços ainda."
    precos = sorted(v["preco"] for v in cal.values())
    t1, t2 = precos[len(precos) // 3], precos[2 * len(precos) // 3]
    meses = [mes] if mes else sorted({k[:7] for k in cal})
    out = []
    for mm in meses:
        a, m = int(mm[:4]), int(mm[5:])
        prim = date(a, m, 1)
        cel = ["　"] * prim.weekday()
        x = prim
        while x.month == m:
            k = x.isoformat()
            cel.append("⬜" if k not in cal else "🟩" if cal[k]["preco"] <= t1 else "🟨" if cal[k]["preco"] <= t2 else "🟥")
            x += timedelta(days=1)
        if all(c in ("　", "⬜") for c in cel):
            continue
        barato = min(((k, v) for k, v in cal.items() if k.startswith(mm)), key=lambda kv: kv[1]["preco"])
        out.append(f"<b>{A.MESES[m - 1]}/{str(a)[2:]}</b> · menor {A.reais(barato[1]['preco'])} em {A.br(barato[0])}")
        out.append("S T Q Q S S D")
        out += ["".join(cel[i:i + 7]) for i in range(0, len(cel), 7)]
        out.append("")
    out.append(f"🟩 até {A.reais(t1)} · 🟨 até {A.reais(t2)} · 🟥 mais caro")
    return "\n".join(out)


def url_grafico(h: dict, titulo: str) -> str | None:
    """Gráfico da evolução como imagem (QuickChart) pra mandar no Telegram sem navegador."""
    import json
    from urllib.parse import quote
    pts = [(e["t"], e["melhor"]) for e in h.get("execucoes", [])][-60:]
    if len(pts) < 2:
        return None
    cfg = {"type": "line", "data": {"labels": [A.d(t).strftime("%d/%m") for t, _ in pts],
           "datasets": [{"label": "menor preço (R$)", "data": [p for _, p in pts], "fill": True,
                         "borderColor": "#16A34A", "backgroundColor": "rgba(22,163,74,0.15)", "pointRadius": 2}]},
           "options": {"title": {"display": True, "text": titulo}, "legend": {"display": False}}}
    return "https://quickchart.io/chart?bkg=white&w=600&h=320&c=" + quote(json.dumps(cfg, separators=(",", ":")))
