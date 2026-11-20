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
            txt.append(f"⚠️ {r['nome']}: {'; '.join(r
