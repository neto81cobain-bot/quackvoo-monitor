"""
QuackVoo Monitor 🦆✈️
Roda uma vez por dia (GitHub Actions), olha o calendário do Google Voos das suas rotas
e te avisa por e-mail/WhatsApp quando o preço cai, bate o alvo ou bate o recorde.
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

AQUI = Path(__file__).parent
HIST = AQUI / "dados" / "historico.json"
DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
DEMO, FORCAR = "--demo" in sys.argv, "--forcar" in sys.argv
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


def cal(o, d, ini, fim, adultos, noites=None):
    global custo_dias
    custo_dias += (A.d(fim) - max(A.d(ini), hoje)).days + 1
    if DEMO:
        return cal_demo(o, d, ini, fim, adultos, noites)
    return fontes.calendario(o, d, ini, fim, adultos, noites, APIFY)


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
            ida_dir = cal(o, dst, ini, fim, ad)
            volta_dir = cal(dst, o, A.mais(ini, n), A.mais(fim, n), ad)
        for hub in r["conexoes"]:
            if hub in (o, dst):
                continue
            try:
                ida = A.combinar_conexao(cal(o, hub, ini, fim, ad), cal(hub, dst, ini, fim1, ad), dias_con)
                if not n:
                    for k, v in ida.items():
                        sugestoes.append({"hub": hub, "dia": k, "total": v["total"], "ida": v, "volta": None})
                    continue
                volta = A.combinar_conexao(cal(dst, hub, A.mais(ini, n), A.mais(fim, n), ad),
                                           cal(hub, o, A.mais(ini, n), A.mais(fim1, n), ad), dias_con)
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
def decidir(res: dict, r: dict, h: dict, dia_resumo: bool) -> list[str]:
    if "melhor" not in res:
        return []
    p, motivos = res["melhor"]["preco"], []
    ult = h["execucoes"][-1]["melhor"] if h.get("execucoes") else None
    rec = h.get("recorde", {}).get("preco")
    alvo = r.get("preco_alvo")
    if ult is None:
        motivos.append("Primeira olhada nessa rota")
    if alvo and p <= alvo and not h.get("avisou_alvo"):
        motivos.append(f"🎯 Abaixo do seu alvo de {A.reais(alvo)}")
    if rec and p < rec:
        motivos.append(f"🏆 Menor preço já visto (antes {A.reais(rec)})")
    elif ult and p <= ult * (1 - r.get("queda_minima", 5) / 100):
        motivos.append(f"📉 Caiu {round((1 - p / ult) * 100)}% desde a última olhada ({A.reais(ult)})")
    eco = res.get("conexao", {}).get("economia", 0)
    if res.get("conexao") and res["conexao"].get("testado_em") == hoje.isoformat() and eco >= CFG_AV.get("economia_minima_conexao", 150):
        motivos.append(f"🔀 Conexão por conta própria economiza {A.reais(eco)}")
    if dia_resumo and not motivos:
        motivos.append("Resumo semanal")
    if FORCAR and not motivos:
        motivos.append("Execução manual")
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
            txt.append(f"⚠️ {r['nome']}: {'; '.join(r['erros'])}"); continue
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

        meses = "".join(f"<tr><td>{x['mes']}</td><td><b>{A.reais(x['menor'])}</b></td><td>{A.br(x['dia'])}</td><td style='color:#888'>{A.reais(x['media'])}</td></tr>" for x in r["meses"])
        top = sorted(r["calendario"].items(), key=lambda kv: kv[1]["preco"])[:5]
        top_html = "".join(f"<li><a href='{v['url']}'>{A.br(k)}</a> — <b>{A.reais(v['preco'])}</b></li>" for k, v in top)
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
 {f"<div style='margin-top:6px'>📅 Melhor semana: <b>{A.br(per['inicio'])} a {A.br(per['fim'])}</b> (média {A.reais(per['media'])})</div>" if per else ''}
 {f"<div>📆 Dia da semana mais barato pra sair: <b>{sem[0][0]}</b>; mais caro: {sem[-1][0]}</div>" if sem else ''}
 <div style="margin-top:10px"><b>Os 5 dias mais baratos</b><ol style="margin:4px 0">{top_html}</ol></div>
 <table style="border-collapse:collapse;margin-top:8px;font-size:14px" cellpadding="4"><tr style="color:#666"><td>Mês</td><td>Menor</td><td>Dia</td><td>Média</td></tr>{meses}</table>
 {con_html}
</div>""")
    corpo = (f"<div style='font-family:Arial,sans-serif;max-width:620px;margin:auto'><h2 style='margin:0'>Quack! 🦆</h2>"
             f"<div style='color:#666'>Relatório de {hoje.strftime('%d/%m/%Y')} · preços do Google Voos (totais, com taxas)</div>{''.join(html)}"
             f"<div style='color:#999;font-size:12px'>Preços mudam a toda hora: confira antes de pagar. Gerado pelo QuackVoo Monitor.</div></div>")
    return assunto, corpo, "\n".join(txt).strip()


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


# ---------------------------------------------------------------- principal
def main():
    global CFG_AV
    cfg = yaml.safe_load((AQUI / "rotas.yaml").read_text(encoding="utf-8"))
    CFG_AV = cfg.get("avisos", {})
    if not DEMO and not APIFY:
        sys.exit("Falta o segredo APIFY_TOKEN (veja o LEIA-ME).")
    hist = json.loads(HIST.read_text()) if HIST.exists() and not DEMO else {}
    hoje_nome = DIAS[hoje.weekday()]
    dia_resumo = sem_acento(str(CFG_AV.get("resumo_semanal", ""))).startswith(hoje_nome[:3])
    dia_conexoes = sem_acento(str(CFG_AV.get("conexoes_toda", "segunda"))).startswith(hoje_nome[:3])

    avisar = []
    for r in cfg["rotas"]:
        h = hist.setdefault(r["nome"], {"execucoes": []})
        testar = FORCAR or DEMO or dia_conexoes or not h.get("conexao")
        try:
            res = analisar(r, testar)
        except fontes.ErroFonte as e:
            res = {"nome": r["nome"], "erros": [str(e)]}
        if "conexao" not in res and h.get("conexao"):
            res["conexao"] = h["conexao"]  # mantém a última conexão testada
        motivos = decidir(res, r, h, dia_resumo)
        if "melhor" in res:
            p = res["melhor"]["preco"]
            print(f"✈️  {r['nome']}: {A.reais(p)} em {res['melhor']['dia']} | {', '.join(motivos) or 'sem novidade'}")
            h["execucoes"] = (h["execucoes"] + [{"t": hoje.isoformat(), "melhor": p, "dia": res["melhor"]["dia"]}])[-120:]
            if not h.get("recorde") or p < h["recorde"]["preco"]:
                h["recorde"] = {"preco": p, "dia": res["melhor"]["dia"], "visto": hoje.isoformat()}
            alvo = r.get("preco_alvo")
            h["avisou_alvo"] = bool(alvo and p <= alvo)
            if res.get("conexao"): h["conexao"] = res["conexao"]
        else:
            print(f"⚠️  {r['nome']}: {'; '.join(res['erros'])}")
        for e in res.get("erros", []):
            if "melhor" in res: print("   ⚠️", e)
        if motivos:
            avisar.append((res, motivos))

    print(f"Custo estimado desta execução: ~{custo_dias} dias de calendário ≈ US$ {custo_dias * 0.0002:.3f} (grátis até US$ 5/mês)")
    HIST.parent.mkdir(exist_ok=True)
    if not DEMO:
        HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=1))

    if not avisar:
        print("Nada novo hoje. Sem aviso."); return
    for res, _ in avisar:
        conferir_horarios(res)
    assunto, html, texto = montar(avisar)
    (AQUI / "dados" / "relatorio.html").write_text(html, encoding="utf-8")
    print("\n" + assunto + "\n" + texto)
    if DEMO and "--enviar" not in sys.argv:
        print("\n(demo: nada enviado; veja dados/relatorio.html)"); return
    if CFG_AV.get("email", True):
        try: print(avisos.email(assunto, html, texto))
        except Exception as e: print("e-mail falhou:", e)
    if CFG_AV.get("whatsapp", True):
        try: print(avisos.whatsapp(assunto + "\n\n" + texto))
        except Exception as e: print("whatsapp falhou:", e)


CFG_AV: dict = {}
if __name__ == "__main__":
    main()
