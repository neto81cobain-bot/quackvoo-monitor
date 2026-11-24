"""
QuackVoo Monitor 🦆✈️
Roda 2x por dia (GitHub Actions), olha o calendário do Google Voos das suas rotas
e te avisa no Telegram/e-mail quando o preço cai, bate o alvo, bate o recorde ou vira promoção.
(A checagem rápida, as promoções dos blogs e os comandos do Telegram ficam no vigia.py.)
Também testa conexões por conta própria (ex.: Manaus → São Paulo + São Paulo → Santa Cruz).

Uso:
  python monitor.py              # execução normal
  python monitor.py --demo       # dados de teste, sem internet, gera dados/relatorio.html
  python monitor.py --forcar     # avisa e testa conexões hoje, mesmo sem queda
"""
import hashlib, json, math, os, random, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

import analise as A
import avisos
import fontes
import inteligencia as I

AQUI = Path(__file__).parent
HIST = AQUI / "dados" / "historico.json"
VIGIA = AQUI / "dados" / "vigia.json"
DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
DEMO, FORCAR = "--demo" in sys.argv, "--forcar" in sys.argv
TESTE = "--teste" in sys.argv  # busca de verdade (com escalas), mas não avisa nem salva
APIFY, SERP = os.getenv("APIFY_TOKEN", ""), os.getenv("SERPAPI_KEY", "")
hoje = date.today()
custo_dias = 0  # dias de calendário consultados (Apify cobra ~US$ 0,20 / 1000)


def sem_acento(s): return s.lower().replace("ç", "c").replace("á", "a").replace("ã", "a").replace("é", "e")


# ---------------------------------------------------------------- dados de teste
def cal_demo(o, d, ini, fim, adultos, noites):
    base = {"MAO": 900, "VVI": 900, "GRU": 180, "VCP": 220, "BSB": 650, "CGB": 700, "LIM": 1100, "STM": 300, "BEL": 300}
    preco0 = (base.get(o, 600) + base.get(d, 600)) * (1.8 if noites else 1) * adultos
    rnd = random.Random(int(hashlib.md5(f"{o}{d}{noites}".encode()).hexdigest()[:8], 16))
    out, x = {}, max(A.d(ini), hoje + timedelta(days=1))
    while x <= A.d(fim):
        k = x.isoformat()
        fator = 1 + 0.18 * math.sin(x.toordinal() / 9) + (0.25 if x.weekday() in (4, 6) else 0) + rnd.uniform(-.08, .08)
        if x.month == 12 and x.day > 18 or (x.month == 2 and 5 <= x.day <= 10): fator += .4
        out[k] = {"preco": round(preco0 * fator), "url": fontes.url_google(o, d, k, A.mais(k, noites) if noites else None)}
        x += timedelta(days=1)
    return out


def cal(o, d, ini, fim, adultos, noites=None, perna=False):
    """perna=True: trecho de escala (busca grátis no Fli primeiro, Apify só se faltar)."""
    global custo_dias
    if DEMO:
        custo_dias += (A.d(fim) - max(A.d(ini), hoje)).days + 1
        return cal_demo(o, d, ini, fim, adultos, noites)
    fonte = "fli_primeiro" if perna else str(CFG_AV.get("fonte", "auto"))
    r = fontes.calendario(o, d, ini, fim, adultos, noites, APIFY, fonte)
    custo_dias = fontes.DIAS_APIFY
    return r


# ---------------------------------------------------------------- análise de uma rota
def analisar(r: dict, testar_conexoes: bool) -> dict:
    o, dst, ad = r["origem"], r["destino"], r.get("adultos", 1)
    ini, fim = [str(x) for x in r["ida_entre"]]
    n = int(r.get("noites") or 0)
    res = {"nome": r["nome"], "origem": o, "destino": dst, "noites": n, "adultos": ad, "erros": []}

    direto = cal(o, dst, ini, fim, ad, n or None)
    res["calendario"] = direto
    if not direto:
        res["erros"].append("O Google não mostrou preços pra essa rota/janela.")
        return res
    dia, info = A.melhor_dia(direto)
    res.update(melhor={"dia": dia, **info}, periodo=A.melhor_periodo(direto), semana=A.por_dia_semana(direto), meses=A.por_mes(direto))

    if testar_conexoes and r.get("conexoes"):
        dias_con = tuple(r.get("conexao_dias", [0, 1]))
        fim1 = A.mais(fim, max(dias_con))
        sugestoes = []
        if n:  # ida e volta: monta ida e volta separadas (direto só ida ou via conexão)
            ida_dir = cal(o, dst, ini, fim, ad, perna=True)
            volta_dir = cal(dst, o, A.mais(ini, n), A.mais(fim, n), ad, perna=True)
        for hub in r["conexoes"]:
            if hub in (o, dst):
                continue
            try:
                ida = A.combinar_conexao(cal(o, hub, ini, fim, ad, perna=True), cal(hub, dst, ini, fim1, ad, perna=True), dias_con)
                if not n:
                    for k, v in ida.items():
                        sugestoes.append({"hub": hub, "dia": k, "total": v["total"], "ida": v, "volta": None})
                    continue
                volta = A.combinar_conexao(cal(dst, hub, A.mais(ini, n), A.mais(fim, n), ad, perna=True),
                                           cal(hub, o, A.mais(ini, n), A.mais(fim1, n), ad, perna=True), dias_con)
                for k in direto:
                    kv = A.mais(k, n)
                    # cada perna escolhe o mais barato: direto só ida ou via conexão
                    op_ida = [("direto", ida_dir[k]["preco"], ida_dir[k])] if k in ida_dir else []
                    if k in ida: op_ida.append((hub, ida[k]["total"], ida[k]))
                    op_vol = [("direto", volta_dir[kv]["preco"], volta_dir[kv])] if kv in volta_dir else []
                    if kv in volta: op_vol.append((hub, volta[kv]["total"], volta[kv]))
                    if not op_ida or not op_vol: continue
                    a, b = min(op_ida, key=lambda x: x[1]), min(op_vol, key=lambda x: x[1])
                    if a[0] == "direto" and b[0] == "direto":
                        sug_hub = "duas só ida"
                    else:
                        sug_hub = hub
                    sugestoes.append({"hub": sug_hub, "dia": k, "total": a[1] + b[1],
                                      "ida": a[2] if a[0] != "direto" else {"direto": a[2]},
                                      "volta": b[2] if b[0] != "direto" else {"direto": b[2]}})
            except fontes.ErroFonte as e:
                res["erros"].append(f"Conexão por {hub}: {e}")
        if sugestoes:
            s = min(sugestoes, key=lambda x: x["total"])
            s["economia"] = info["preco"] - s["total"]
            s["vs_mesmo_dia"] = direto.get(s["dia"], {}).get("preco")
            s["testado_em"] = hoje.isoformat()
            res["conexao"] = s
    return res


# ---------------------------------------------------------------- decisão de avisar
def ref_vigia(r: dict, h: dict) -> float | None:
    """Preço que o vigia (checagem rápida) já avisou depois da última busca completa."""
    v = VIG.get("rapida", {}).get(r["nome"], {})
    if v.get("alertou") and v["alertou"].get("quando", "") > h.get("ultima_iso", ""):
        return v["alertou"]["preco"]
    return None


def decidir(res: dict, r: dict, h: dict, dia_resumo: bool) -> list[str]:
    if "melhor" not in res:
        return []
    p, motivos = res["melhor"]["preco"], []
    ult = h["execucoes"][-1]["melhor"] if h.get("execucoes") else None
    rv = ref_vigia(r, h)
    if rv and ult: ult = min(ult, rv)
    rec = h.get("recorde", {}).get("preco")
    if rv and rec: rec = min(rec, rv)
    alvo = r.get("preco_alvo")
    if ult is None:
        motivos.append("Primeira olhada nessa rota")
    if alvo and p <= alvo and not h.get("avisou_alvo"):
        motivos.append(f"🎯 Abaixo do seu alvo de {A.reais(alvo)}")
    if rec and p < rec:
        motivos.append(f"🏆 Menor preço já visto (antes {A.reais(rec)})")
    elif ult and p <= ult * (1 - r.get("queda_minima", 5) / 100):
        motivos.append(f"📉 Caiu {round((1 - p / ult) * 100)}% desde a última olhada ({A.reais(ult)})")
    v = res.get("veredito")
    if v and v["nivel"] == "promo" and h.get("promo_avisada") != p and not motivos:
        motivos.append(f"🔥 Promoção forte: {round(v['desconto'] * 100)}% abaixo do normal")
    eco = res.get("conexao", {}).get("economia", 0)
    if res.get("conexao") and res["conexao"].get("testado_em") == hoje.isoformat() and eco >= CFG_AV.get("economia_minima_conexao", 150):
        motivos.append(f"🔀 Conexão por conta própria economiza {A.reais(eco)}")
    if dia_resumo and not motivos:
        motivos.append("Resumo semanal")
    if FORCAR and not motivos:
        motivos.append("Execução manual")
    if CFG_AV.get("relatorio_toda_busca", False) and not motivos:
        motivos.append("Relatório da busca (sem queda desde a última)")
    return motivos


# ---------------------------------------------------------------- textos
def texto_conexao(s: dict, o: str, dst: str, n: int) -> list[str]:
    hub = s["hub"]
    def perna(rotulo, x, a, b, dia1):
        if not x: return []
        if "direto" in x:
            return [f"{rotulo}: {a}→{b} só ida {A.br(dia1)} {A.reais(x['direto']['preco'])}"]
        dorme = " (dorme em " + hub + ")" if x["data2"] != dia1 else ""
        return [f"{rotulo}: {a}→{hub} {A.br(dia1)} {A.reais(x['p1']['preco'])} + {hub}→{b} {A.br(x['data2'])} {A.reais(x['p2']['preco'])}{dorme}"]
    titulo = "Duas passagens só de ida" if hub == "duas só ida" else f"Via {hub}"
    linhas = [f"{titulo}, total {A.reais(s['total'])}"]
    linhas += perna("Ida", s["ida"], o, dst, s["dia"])
    if n: linhas += perna("Volta", s["volta"], dst, o, A.mais(s["dia"], n))
    return linhas


def montar(res_avisar: list[tuple[dict, list[str]]]) -> tuple[str, str, str]:
    principais = [r for r, _ in res_avisar if "melhor" in r]
    p0 = principais[0]
    assunto = f"🦆 Quack! {p0['origem']}→{p0['destino']} a partir de {A.reais(p0['melhor']['preco'])}" + (f" (+{len(principais)-1} rotas)" if len(principais) > 1 else "")
    txt, html = [], []
    for r, motivos in res_avisar:
        if "melhor" not in r:
            txt.append(f"⚠️ {r['nome']}: {'; '.join(r['erros'])}")
            continue
        m, per = r["melhor"], r.get("periodo")
        tipo = f"ida e volta, {r['noites']} noites" if r["noites"] else "só ida"
        txt += [f"✈️ *{r['nome']}* ({tipo})", *[f"• {x}" for x in motivos],
                f"Mais barato: {A.reais(m['preco'])} saindo {A.br(m['dia'])}"]
        if per: txt.append(f"Melhor semana: {A.br(per['inicio'])} a {A.br(per['fim'])} (média {A.reais(per['media'])})")
        sem = sorted(r.get("semana", []), key=lambda x: x[1])
        if sem: txt.append(f"Dia mais barato pra sair: {sem[0][0]}")
        c = r.get("conexao")
        if c and c["economia"] <= 0:
            txt.append(f"🔀 Testei conexões ({c['hub']} foi a melhor): o voo comum segue mais barato.")
        if c and c["economia"] > 0:
            txt += ["🔀 Dica: " + " | ".join(texto_conexao(c, r["origem"], r["destino"], r["noites"])) + f" → economiza {A.reais(c['economia'])}"]
            txt += [f"   {x}" for x in c.get("horarios", [])]
        txt += [f"🔗 {m['url']}", ""]

        hh = HIST_ATUAL.get(r["nome"], {})
        fer = I.feriados_no_periodo(min(r["calendario"]), max(r["calendario"]))
        v = r.get("veredito")
        cores = {"promo": ("#FEF2F2", "#B91C1C"), "bom": ("#F0FDF4", "#15803D"), "normal": ("#F9FAFB", "#374151"), "caro": ("#FFF7ED", "#C2410C")}
        ver_html = ""
        if v:
            fundo, cor = cores[v["nivel"]]
            ver_html = (f"<div style='background:{fundo};border-radius:10px;padding:10px 12px;margin:8px 0'>"
                        f"<div style='font-weight:800;color:{cor};font-size:16px'>{v['emoji']} {v['rotulo']}</div>"
                        f"<div style='font-weight:700;margin-top:2px'>{v['conselho']}</div>"
                        f"<div style='color:#4b5563;font-size:13px;margin-top:4px'>{' · '.join(v['detalhes'])}</div></div>")
        voo = r.get("voo")
        voo_html = (f"<div style='color:#374151;font-size:14px'>🛫 {voo['cia']} · sai {voo['saida'][-5:]} · chega {voo['chegada'][-5:]} · "
                    + ("direto" if not voo["paradas"] else f"{voo['paradas']} parada(s)") + "</div>") if voo and voo.get("cia") else ""
        evol = I.svg_evolucao(hh, m["preco"])
        evol_html = f"<div style='margin-top:10px'><b>Evolução do menor preço</b>{evol}</div>" if evol else ""
        calor_html = I.html_calor(r["calendario"], fer)
        fer_html = ""
        if fer:
            itens = []
            for k, nome_f in fer[:6]:
                janela = {x: y for x, y in r["calendario"].items() if 0 <= (A.d(k) - A.d(x)).days <= 2}
                if janela:
                    kk, vv = min(janela.items(), key=lambda kv: kv[1]["preco"])
                    itens.append(f"{nome_f} {A.d(k).strftime('%d/%m')}: saindo {A.br(kk)} por <b>{A.reais(vv['preco'])}</b>")
            if itens:
                fer_html = "<div style='margin-top:8px'>🎉 <b>Feriados no período</b><br>" + "<br>".join(itens) + "</div>"
        comp = " · ".join(f"<a href='{u}'>{t}</a>" for t, u in I.links_comparar(r["origem"], r["destino"], m["dia"], r["noites"], r["adultos"]))
        meses = "".join(f"<tr><td>{x['mes']}</td><td><b>{A.reais(x['menor'])}</b></td><td>{A.br(x['dia'])}</td><td style='color:#888'>{A.reais(x['media'])}</td></tr>" for x in r["meses"])
        top = sorted(r["calendario"].items(), key=lambda kv: kv[1]["preco"])[:5]
        top_html = "".join(f"<li><a href='{x['url']}'>{A.br(k)}</a> — <b>{A.reais(x['preco'])}</b> <span style='color:#2563EB;font-size:12px'>{I.etiqueta_feriado(k, fer)}</span></li>" for k, x in top)
        con_html = ""
        if c and c["economia"] > 0:
            con_html = (f"<div style='background:#EEF6FF;border-radius:10px;padding:12px;margin-top:12px'><b>🔀 Conexão por conta própria</b><br>"
                        + "<br>".join(texto_conexao(c, r["origem"], r["destino"], r["noites"])) + f"<br><b style='color:#16A34A'>Economia: {A.reais(c['economia'])}</b>" + "".join(f"<br>{x}" for x in c.get("horarios", []))
                        + "<br><small>São passagens separadas: se o 1º voo atrasar, a cia do 2º não te protege, e a mala precisa ser despachada de novo. Deixe 4h+ de folga ou durma na conexão.</small></div>")
        html.append(f"""
<div style="border:1px solid #e5e7eb;border-radius:14px;padding:16px;margin:14px 0">
 <div style="font-size:18px;font-weight:700">✈️ {r['nome']} <span style="font-weight:400;color:#666;font-size:13px">· {tipo} · {r['adultos']} adulto(s)</span></div>
 <div style="margin:8px 0;color:#374151">{'<br>'.join(motivos)}</div>
 <div style="font-size:28px;font-weight:800;color:#16A34A">{A.reais(m['preco'])}</div>
 <div>saindo <b>{A.br(m['dia'])}</b> · <a href="{m['url']}">abrir no Google Voos</a></div>
 {voo_html}
 {ver_html}
 <div style="font-size:13px;color:#6b7280">Comparar: {comp}</div>
 {f"<div style='margin-top:6px'>📅 Melhor semana: <b>{A.br(per['inicio'])} a {A.br(per['fim'])}</b> (média {A.reais(per['media'])})</div>" if per else ''}
 {f"<div>📆 Dia da semana mais barato pra sair: <b>{sem[0][0]}</b>; mais caro: {sem[-1][0]}</div>" if sem else ''}
 <div style="margin-top:10px"><b>Os 5 dias mais baratos</b><ol style="margin:4px 0">{top_html}</ol></div>
 {fer_html}
 <table style="border-collapse:collapse;margin-top:8px;font-size:14px" cellpadding="4"><tr style="color:#666"><td>Mês</td><td>Menor</td><td>Dia</td><td>Média</td></tr>{meses}</table>
 {evol_html}
 {calor_html}
 {con_html}
</div>""")
    corpo = (f"<div style='font-family:Arial,sans-serif;max-width:620px;margin:auto'><h2 style='margin:0'>Quack! 🦆</h2>"
             f"<div style='color:#666'>Relatório de {hoje.strftime('%d/%m/%Y')} · preços do Google Voos (totais, com taxas)</div>{''.join(html)}"
             f"<div style='color:#999;font-size:12px'>Preços mudam a toda hora: confira antes de pagar. Gerado pelo QuackVoo Monitor.</div></div>")
    return assunto, corpo, "\n".join(txt).strip()


def montar_telegram(res_avisar: list[tuple[dict, list[str]]]) -> str:
    linhas = [
        "<b>Quack! 🦆</b>",
        f"<i>Relatório de {hoje.strftime('%d/%m/%Y')} · preços do Google Voos (totais, com taxas)</i>",
        "",
    ]
    for r, motivos in res_avisar:
        if "melhor" not in r:
            linhas.append(f"⚠️ <b>{r['nome']}</b>: {'; '.join(r['erros'])}")
            linhas.append("")
            continue

        m, per = r["melhor"], r.get("periodo")
        tipo = f"ida e volta, {r['noites']} noites" if r["noites"] else "só ida"
        sem = sorted(r.get("semana", []), key=lambda x: x[1])
        c = r.get("conexao")

        linhas.append(f"✈️ <b>{r['nome']}</b> · <i>{tipo} · {r['adultos']} adulto(s)</i>")
        if motivos:
            linhas.extend(motivos)
        linhas.append("")
        linhas.append(f"<b>{A.reais(m['preco'])}</b>")
        linhas.append(f"saindo <b>{A.br(m['dia'])}</b> · <a href=\"{m['url']}\">abrir no Google Voos</a>")
        if r.get("veredito"):
            v = r["veredito"]
            linhas += [f"{v['emoji']} <b>{v['rotulo']}</b> — {v['conselho']}", "<i>" + " · ".join(v["detalhes"]) + "</i>"]

        if per:
            linhas.append(f"📅 Melhor semana: <b>{A.br(per['inicio'])} a {A.br(per['fim'])}</b> (média {A.reais(per['media'])})")
        if sem:
            linhas.append(f"📆 Dia da semana mais barato pra sair: <b>{sem[0][0]}</b>; mais caro: {sem[-1][0]}")

        top = sorted(r["calendario"].items(), key=lambda kv: kv[1]["preco"])[:5]
        if top:
            linhas.append("")
            linhas.append("<b>Os 5 dias mais baratos</b>")
            for idx, (k, v) in enumerate(top, 1):
                linhas.append(f"{idx}. <a href=\"{v['url']}\">{A.br(k)}</a> — <b>{A.reais(v['preco'])}</b>")

        if r.get("meses"):
            linhas.append("")
            linhas.append("<pre>")
            linhas.append(f"{'Mês':<7} {'Menor':>9} {'Dia':<10} {'Média':>9}")
            for x in r["meses"]:
                linhas.append(f"{str(x['mes'])[:7]:<7} {A.reais(x['menor']):>9} {A.br(x['dia'])[:10]:<10} {A.reais(x['media']):>9}")
            linhas.append("</pre>")

        if c and c.get("economia", 0) > 0:
            linhas.append("")
            linhas.append("🔀 <b>Conexão por conta própria</b>")
            linhas.extend(texto_conexao(c, r["origem"], r["destino"], r["noites"]))
            linhas.append(f"<b>Economia: {A.reais(c['economia'])}</b>")
            linhas.extend(c.get("horarios", []))
            linhas.append("<i>São passagens separadas: se o 1º voo atrasar, a cia do 2º não te protege, e a mala precisa ser despachada de novo. Deixe 4h+ de folga ou durma na conexão.</i>")

        linhas.append("")
        linhas.append("────────────────────────")
        linhas.append("")

    linhas.append("<i>Preços mudam a toda hora: confira antes de pagar. Gerado pelo QuackVoo Monitor.</i>")
    return "\n".join(linhas).strip()


def conferir_horarios(res: dict):
    """Confere na SerpAPI os horários dos 2 trechos da ida da conexão (gasta 2 buscas)."""
    c = res.get("conexao")
    if DEMO or not SERP or not c or c["economia"] <= 0 or "p1" not in (c.get("ida") or {}) or c.get("horarios"):
        return
    hub, ida = c["hub"], c["ida"]
    v1 = fontes.detalhes_voo(res["origem"], hub, c["dia"], res["adultos"], SERP)
    v2 = fontes.detalhes_voo(hub, res["destino"], ida["data2"], res["adultos"], SERP)
    if not (v1 and v2):
        return
    h = [f"{res['origem']}→{hub}: {v1['cia']} sai {v1['saida'][-5:]} chega {v1['chegada'][-5:]}",
         f"{hub}→{res['destino']}: {v2['cia']} sai {v2['saida'][-5:]} chega {v2['chegada'][-5:]}"]
    gap = (datetime.fromisoformat(v2["saida"].replace(" ", "T")) - datetime.fromisoformat(v1["chegada"].replace(" ", "T"))).total_seconds() / 3600
    if gap < 0: h.append("⚠️ O 2º voo sai antes do 1º chegar: escolha outro horário ou durma na conexão.")
    elif gap < 4: h.append(f"⚠️ Só {gap:.1f} h entre os voos: arriscado com passagens separadas (ideal 4 h+).")
    else: h.append(f"✅ {gap:.1f} h entre os voos.")
    c["horarios"] = h


def legenda_e_botoes(r: dict, motivos: list[str]) -> tuple[str, list[list[tuple[str, str]]]]:
    """Legenda curta da foto + botões com os links (Google Voos e escalas)."""
    if "melhor" not in r:
        return f"⚠️ <b>{r['nome']}</b>: {'; '.join(r['erros'])}", []
    m = r["melhor"]
    legenda = f"✈️ <b>{r['nome']}</b> · <b>{A.reais(m['preco'])}</b> saindo {A.br(m['dia'])}\n" + "\n".join(motivos)
    v = r.get("veredito")
    if v:
        legenda += f"\n\n{v['emoji']} <b>{v['rotulo']}</b> — {v['conselho']}"
    botoes = [[(f"🔎 Abrir {A.br(m['dia'])} no Google Voos", m["url"])],
              [(f"🔁 {t}", u) for t, u in I.links_comparar(r["origem"], r["destino"], m["dia"], r["noites"], r["adultos"])]]
    top = sorted(r["calendario"].items(), key=lambda kv: kv[1]["preco"])[1:5]
    if top:
        botoes.append([(f"{A.d(k).strftime('%d/%m')} · {A.reais(v['preco'])}", v["url"]) for k, v in top[:2]])
        botoes.append([(f"{A.d(k).strftime('%d/%m')} · {A.reais(v['preco'])}", v["url"]) for k, v in top[2:4]])
    c = r.get("conexao")
    if c and c.get("economia", 0) > 0 and "p1" in (c.get("ida") or {}):
        ida, hub = c["ida"], c["hub"]
        botoes.append([(f"🔀 {r['origem']}→{hub} {A.d(c['dia']).strftime('%d/%m')}", ida["p1"]["url"]),
                       (f"{hub}→{r['destino']} {A.d(ida['data2']).strftime('%d/%m')}", ida["p2"]["url"])])
    return legenda, botoes


def _h(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _dia(k: str) -> str:
    """'sáb 29/05'"""
    return f"{A.SEMANA[A.d(k).weekday()]} {A.d(k).strftime('%d/%m')}"


def _link(url: str, texto: str) -> str:
    return f'<a href="{_h(url)}">{texto}</a>'


VENDEDORES_RJ = ("123milhas", "123 milhas", "maxmilhas", "max milhas")


def mensagem_bonita(r: dict, motivos: list[str], links_cal: bool = True) -> tuple[str, list]:
    """Relatório em texto pro Telegram: o essencial em cima, tudo clicável, detalhes recolhidos."""
    if "melhor" not in r:
        return f"⚠️ <b>{_h(r['nome'])}</b>\n{_h('; '.join(r['erros']))}", []
    m, cal = r["melhor"], r["calendario"]
    nome = _h(r["nome"].replace("->", "→"))
    tipo = f"ida e volta · {r['noites']} noites" if r["noites"] else "só ida"
    dias = sorted(cal)
    hh = HIST_ATUAL.get(r["nome"], {})
    L = [f"✈️ <b>{nome}</b>",
         f"<i>{tipo} · {r['adultos']} adulto{'s' if r['adultos'] > 1 else ''} · {A.d(dias[0]).strftime('%d/%m')} a {A.d(dias[-1]).strftime('%d/%m')}</i>", ""]
    L += [_h(x) for x in motivos if x not in ("Execução manual", "Relatório da busca (sem queda desde a última)")]
    L.append(f"💰 <b>{_link(m['url'], A.reais(m['preco']))}</b> · {_dia(m['dia'])}")
    voo = r.get("voo")
    if voo and voo.get("cia"):
        L.append(f"<i>{_h(voo['cia'])} · {voo['saida'][-5:]} → {voo['chegada'][-5:]} · " + ("direto" if not voo["paradas"] else f"{voo['paradas']} parada{'s' if voo['paradas'] > 1 else ''}") + "</i>")
    spark = I.sparkline([e["melhor"] for e in hh.get("execucoes", [])] + [m["preco"]])
    if spark:
        L.append(f"<code>{spark}</code> <i>últimas buscas</i>")
    v = r.get("veredito")
    if v:
        L += ["", f"{v['emoji']} <b>{v['rotulo']}</b> — {_h(v['conselho'])}", f"<i>{_h(' · '.join(v['detalhes'][:3]))}</i>"]

    # onde comprar (vendedores do Google pro dia mais barato)
    vend = r.get("vendedores") or []
    if vend:
        L += ["", f"🛒 <b>Onde comprar</b> ({_dia(m['dia'])})"]
        for x in vend[:6]:
            alerta = " ⚠️" if x["vendedor"].lower().startswith(VENDEDORES_RJ) else ""
            L.append(f"• {_link(x['url'], _h(x['vendedor']))} {A.reais(x['preco']) if x.get('preco') else ''}{alerta}")

    # dias mais baratos, agrupados por preço e clicáveis
    top = sorted(cal.items(), key=lambda kv: (kv[1]["preco"], kv[0]))[:8]
    grupos: dict = {}
    for k, x in top:
        grupos.setdefault(x["preco"], []).append((k, x))
    L += ["", "📆 <b>Dias mais baratos</b>"]
    for preco, itens in list(grupos.items())[:3]:
        L.append(f"<b>{A.reais(preco)}</b>  " + " · ".join(_link(x["url"], _dia(k)) for k, x in sorted(itens)[:5]))

    per = r.get("periodo")
    fer = I.feriados_no_periodo(dias[0], dias[-1])
    extras = []
    if per and per["inicio"] in cal:
        extras.append(f"🗓️ Melhor semana: {_link(cal[per['inicio']]['url'], A.d(per['inicio']).strftime('%d/%m') + ' a ' + A.d(per['fim']).strftime('%d/%m'))} · média {A.reais(per['media'])}")
    for kf, nome_f in fer[:3]:
        janela = {x: y for x, y in cal.items() if 0 <= (A.d(kf) - A.d(x)).days <= 2}
        if janela:
            kk, vv = min(janela.items(), key=lambda kv: kv[1]["preco"])
            extras.append(f"🎉 {nome_f} ({A.d(kf).strftime('%d/%m')}): {_link(vv['url'], A.reais(vv['preco']))} saindo {_dia(kk)}")
    if extras:
        L += [""] + extras

    c = r.get("conexao")
    if c and c.get("economia", 0) > 0 and "p1" in (c.get("ida") or {}):
        ida, hub = c["ida"], c["hub"]
        L += ["", f"🔀 <b>Escala por conta própria: {A.reais(c['total'])}</b> (economia de {A.reais(c['economia'])})",
              _link(ida["p1"]["url"], f"{r['origem']}→{hub} {_dia(c['dia'])}") + f" {A.reais(ida['p1']['preco'])}  +  "
              + _link(ida["p2"]["url"], f"{hub}→{r['destino']} {_dia(ida['data2'])}") + f" {A.reais(ida['p2']['preco'])}"]
        L += [f"<i>{_h(x)}</i>" for x in c.get("horarios", [])]
        L.append("<i>Passagens separadas: deixe 4 h+ de folga ou durma na escala.</i>")

    # outros sites com a mesma busca pronta (recolhido)
    sites = I.links_sites(r["origem"], r["destino"], m["dia"], r["noites"], r["adultos"])
    blocos = [f"🔎 <b>Mesma busca ({_dia(m['dia'])}) em outros sites</b>"]
    for grupo, lista in sites.items():
        itens = [_link(u, _h(n)) + (" ⚠️" if nota == I.AVISO_RJ else "") for n, u, nota in lista]
        blocos.append(f"<b>{grupo}:</b> " + " · ".join(itens))
    blocos.append("<i>⚠️ 123milhas e MaxMilhas estão em recuperação judicial.</i>")

    # meses e calendário (recolhido)
    det = ["<b>Por mês</b>"]
    for x in r.get("meses", []):
        det.append(f"{x['mes']} · <b>{A.reais(x['menor'])}</b> {_link(cal[x['dia']]['url'], _dia(x['dia']))} · média {A.reais(x['media'])}")
    sem = sorted(r.get("semana", []), key=lambda x: x[1])
    if sem:
        det.append(f"Mais barato sair: <b>{sem[0][0]}</b> · mais caro: {sem[-1][0]}")
    calendario = I.texto_calor(cal, links=links_cal)
    previa = "\n".join(L + blocos + det) + calendario
    if avisos.tamanho_visivel(previa) > 3900:  # período muito longo: calendário só nos 3 meses mais baratos
        meses_bons = sorted({k[:7] for k, _ in sorted(cal.items(), key=lambda kv: kv[1]["preco"])[:40]})[:3]
        calendario = "\n".join(I.texto_calor(cal, mm, links=links_cal) for mm in meses_bons)
    det += ["", "<b>Calendário</b> <i>(toque num quadradinho pra abrir o dia)</i>" if links_cal else "<b>Calendário</b>", calendario]
    L += ["", "<blockquote expandable>" + "\n".join(blocos) + "</blockquote>",
          "<blockquote expandable>" + "\n".join(det) + "</blockquote>",
          "<i>Preços com taxas. Confira antes de pagar.</i>"]

    i = r.get("indice", 1)
    alvo = max(100, int(m["preco"] * 0.9 // 50 * 50))
    botoes = [[(f"🔎 Abrir {_dia(m['dia'])} no Google Voos", m["url"])],
              [(f"🎯 Alvo {A.reais(alvo)}", f"/alvo {i} {alvo}"), ("✅ Comprei", f"/comprei {i} {m['preco']} {A.d(m['dia']).strftime('%d/%m/%Y')}")],
              [("⏸️ Pausar 7 dias", f"/pausar {i} 7"), ("📊 Status", "/status")]]
    return "\n".join(L), botoes


def enviar_telegram(avisar: list[tuple[dict, list[str]]]) -> None:
    """Uma mensagem por rota: texto organizado com links (padrão) ou imagem (avisos.formato_telegram: imagem)."""
    for res, motivos in avisar:
        som = I.forte(motivos, res.get("veredito"))
        silencioso = not som or (avisos.hora_silenciosa() and not (res.get("veredito") or {}).get("nivel") == "promo")
        if CFG_AV.get("formato_telegram", "texto") != "imagem":
            enviado = False
            for links_cal in (True, False):  # se o Telegram recusar tantos links, manda o calendário sem link
                try:
                    texto, botoes = mensagem_bonita(res, motivos, links_cal)
                    avisos.mensagem(texto, botoes, silencioso=silencioso)
                    print("Telegram: mensagem enviada" + ("" if links_cal else " (calendário sem links)")); enviado = True; break
                except Exception as e:
                    print(f"mensagem (links_cal={links_cal}) falhou: {e}")
            if enviado:
                continue
        try:
            _, html, _ = montar([(res, motivos)])
            legenda, botoes = legenda_e_botoes(res, motivos)
            print(avisos.telegram_foto(avisos.html_para_png(html), legenda, botoes, silencioso=silencioso))
        except Exception as e:
            print(f"imagem falhou ({e}); mandando em texto")
            print(avisos.telegram(montar_telegram([(res, motivos)])))


# ---------------------------------------------------------------- principal
def main():
    global CFG_AV
    cfg = yaml.safe_load((AQUI / "rotas.yaml").read_text(encoding="utf-8"))
    CFG_AV = cfg.get("avisos", {})
    if not DEMO and not APIFY:
        sys.exit("Falta o segredo APIFY_TOKEN (veja o LEIA-ME).")
    global VIG, HIST_ATUAL
    hist = json.loads(HIST.read_text()) if HIST.exists() and not DEMO else {}
    HIST_ATUAL = hist
    try: VIG = json.loads(VIGIA.read_text()) if VIGIA.exists() else {}
    except ValueError: VIG = {}
    hoje_nome = DIAS[hoje.weekday()]
    dia_resumo = sem_acento(str(CFG_AV.get("resumo_semanal", ""))).startswith(hoje_nome[:3])
    dia_conexoes = sem_acento(str(CFG_AV.get("conexoes_toda", "segunda"))).startswith(hoje_nome[:3])

    avisar, erros_meta = [], []
    economia = (VIG.get("apify") or {}).get("pct", 0) >= 0.95  # crédito quase no fim: não testa conexões
    for indice, r in enumerate(cfg["rotas"], 1):
        if r.get("pausada_ate") and str(r["pausada_ate"]) > hoje.isoformat():
            print(f"⏸️  {r['nome']}: pausada até {r['pausada_ate']}"); continue
        if r.get("ativa") is False:
            print(f"⏸️  {r['nome']}: pausada no painel"); continue
        h = hist.setdefault(r["nome"], {"execucoes": []})
        # se a rota mudou (origem, destino, ida/volta, adultos), o histórico antigo não vale mais
        assinatura = f"{r['origem']}>{r['destino']}|n{int(r.get('noites') or 0)}|a{r.get('adultos', 1)}"
        if h.get("assinatura") != assinatura:
            if h.get("assinatura"):
                print(f"↺  {r['nome']}: rota mudou ({h['assinatura']} → {assinatura}), recomeçando o histórico")
            h.clear(); h.update({"execucoes": [], "assinatura": assinatura})
        ja_testou_hoje = (h.get("conexao") or {}).get("testado_em") == hoje.isoformat()
        testar = (FORCAR or DEMO or TESTE or (dia_conexoes and not ja_testou_hoje) or not h.get("conexao")) and not economia
        try:
            res = analisar(r, testar)
        except fontes.ErroFonte as e:
            res = {"nome": r["nome"], "erros": [str(e)]}
        if "conexao" not in res and h.get("conexao"):
            res["conexao"] = h["conexao"]  # mantém a última conexão testada
        res["indice"] = indice
        if "melhor" in res:
            res["veredito"] = I.veredito(res["melhor"]["preco"], res["calendario"], h, r)
        motivos = decidir(res, r, h, dia_resumo)
        if motivos and "melhor" in res and SERP and not DEMO:
            # opinião do Google + voo de verdade (cia, horário) do melhor dia: 1 busca SerpAPI por aviso
            m = res["melhor"]
            voo = fontes.detalhes_voo(r["origem"], r["destino"], m["dia"], r.get("adultos", 1), SERP,
                                      A.mais(m["dia"], res["noites"]) if res["noites"] else None)
            if voo:
                res["voo"] = voo
                if not res["noites"]:
                    res["vendedores"] = fontes.onde_comprar(r["origem"], r["destino"], m["dia"], r.get("adultos", 1), SERP, voo.get("booking_token"))
                if voo.get("google"):
                    res["veredito"] = I.veredito(m["preco"], res["calendario"], h, r, voo["google"])
        if "melhor" in res:
            p = res["melhor"]["preco"]
            print(f"✈️  {r['nome']}: {A.reais(p)} em {res['melhor']['dia']} | {', '.join(motivos) or 'sem novidade'}")
            h["execucoes"] = (h["execucoes"] + [{"t": hoje.isoformat(), "melhor": p, "dia": res["melhor"]["dia"]}])[-120:]
            if not h.get("recorde") or p < h["recorde"]["preco"]:
                h["recorde"] = {"preco": p, "dia": res["melhor"]["dia"], "visto": hoje.isoformat()}
            alvo = r.get("preco_alvo")
            h["avisou_alvo"] = bool(alvo and p <= alvo)
            h["ultimo_cal"] = {k: v["preco"] for k, v in sorted(res["calendario"].items())}
            h["ultima_iso"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if any(x.startswith("🔥") for x in motivos) or (res.get("veredito") or {}).get("nivel") == "promo":
                h["promo_avisada"] = p
            if res.get("conexao"): h["conexao"] = res["conexao"]
        else:
            print(f"⚠️  {r['nome']}: {'; '.join(res['erros'])}")
            erros_meta.append(f"{r['nome']}: {'; '.join(res['erros'])}")
        for e in res.get("erros", []):
            if "melhor" in res:
                print("   ⚠️", e)
        if motivos:
            avisar.append((res, motivos))

    print(f"Custo estimado desta execução: ~{custo_dias} dias de calendário na Apify ≈ US$ {custo_dias * 0.0002:.3f} (grátis até US$ 5/mês)"
          + (" · Fli (grátis) usado nas escalas" if "fli" in fontes.FONTE_USADA else ""))
    HIST.parent.mkdir(exist_ok=True)
    hist["_meta"] = {"ultima": datetime.now(timezone.utc).isoformat(timespec="seconds"), "custo_dias": custo_dias, "erros": erros_meta}
    if not DEMO and not TESTE:
        HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=1))

    if not avisar:
        print("Nada novo hoje. Sem aviso."); return
    for res, _ in avisar:
        conferir_horarios(res)
    assunto, html, texto = montar(avisar)
    (AQUI / "dados" / "relatorio.html").write_text(html, encoding="utf-8")
    print("\n" + assunto + "\n" + texto)
    if TESTE:
        print("\n(teste: nada enviado nem salvo)"); return
    if DEMO and "--enviar" not in sys.argv:
        print("\n(demo: nada enviado; veja dados/relatorio.html)"); return
    if CFG_AV.get("email", True):
        try: print(avisos.email(assunto, html, texto))
        except Exception as e: print("e-mail falhou:", e)
    if CFG_AV.get("telegram", CFG_AV.get("whatsapp", True)):
        try: enviar_telegram(avisar)
        except Exception as e: print("telegram falhou:", e)


CFG_AV: dict = {}
VIG: dict = {}
HIST_ATUAL: dict = {}
if __name__ == "__main__":
    main()
