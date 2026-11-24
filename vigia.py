"""
QuackVoo Vigia 👀 — roda a cada ~15 min (GitHub Actions) e cuida do que não pode esperar a busca completa:

  • comandos do Telegram (/status, /agora, /buscar, /comprei, /alvo, /pausar…)
  • promoções dos blogs de passagem que falam dos seus destinos (grátis)
  • checagem rápida a cada 2 h só nos dias mais baratos (gasta pouco da Apify)
  • rede de segurança de 24 h depois que você compra (regra da ANAC)
  • saúde: refaz a busca se o GitHub pular o horário, avisa se a Apify/SerpAPI estiver acabando

Uso:  python vigia.py            (normal)
      python vigia.py --tudo     (ignora os intervalos e faz todas as tarefas agora)
"""
import json, os, re, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

import analise as A
import avisos
import fontes
import inteligencia as I
import promos
from aeroportos import nome as nome_aero

AQUI = Path(__file__).parent
HIST, VIGIA, ROTAS = AQUI / "dados" / "historico.json", AQUI / "dados" / "vigia.json", AQUI / "rotas.yaml"
WF = AQUI / ".github" / "workflows" / "quackvoo.yml"
APIFY, SERP = os.getenv("APIFY_TOKEN", ""), os.getenv("SERPAPI_KEY", "")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
REPO, GH_TOKEN = os.getenv("GITHUB_REPOSITORY", ""), os.getenv("GITHUB_TOKEN", "")
BRT = timezone(timedelta(hours=-3))
TUDO = "--tudo" in sys.argv
AGORA = datetime.now(timezone.utc)
HOJE = AGORA.astimezone(BRT).date()
VERSAO_COMANDOS = 3

cfg = yaml.safe_load(ROTAS.read_text(encoding="utf-8")) or {}
cfg.setdefault("rotas", []); cfg.setdefault("avisos", {})
AV = cfg["avisos"]
hist = json.loads(HIST.read_text()) if HIST.exists() else {}
try:
    est = json.loads(VIGIA.read_text()) if VIGIA.exists() else {}
except ValueError:
    est = {}
mudou_rotas = False


# ---------------------------------------------------------------- utilidades
def iso(dt: datetime) -> str: return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
def de_iso(s: str) -> datetime: return datetime.fromisoformat(s)
def minutos_desde(chave: str) -> float:
    return 1e9 if not est.get(chave) else (AGORA - de_iso(est[chave])).total_seconds() / 60
def hora_br(s: str) -> str: return de_iso(s).astimezone(BRT).strftime("%d/%m %H:%M")


def enviar(texto, botoes=None, forte=False):
    """Som só quando importa; de madrugada só promoção forte toca."""
    urgente = texto.startswith("🛟") or "🔥" in texto
    silencioso = not forte or (avisos.hora_silenciosa() and not urgente)
    try:
        avisos.mensagem(texto, botoes, silencioso=silencioso)
    except Exception as e:
        print("Telegram falhou:", e)


def ativas():
    return [(i, r) for i, r in enumerate(cfg["rotas"], 1) if r.get("ativa") is not False]


def github(metodo, caminho, **kw):
    if not (REPO and GH_TOKEN):
        raise RuntimeError("sem GITHUB_TOKEN (só funciona dentro do GitHub Actions)")
    r = requests.request(metodo, f"https://api.github.com/repos/{REPO}/{caminho}", timeout=30,
                         headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}, **kw)
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub {r.status_code}: {r.text[:150]}")
    return r.json() if r.text else {}


def disparar_busca(forcar: bool) -> None:
    github("POST", "actions/workflows/quackvoo.yml/dispatches", json={"ref": "main", "inputs": {"forcar": "true" if forcar else "false"}})


def busca_rodando() -> bool:
    try:
        runs = github("GET", "actions/workflows/quackvoo.yml/runs?per_page=3").get("workflow_runs", [])
        return any(x["status"] in ("queued", "in_progress", "waiting", "pending") for x in runs)
    except Exception:
        return False


def preco_ref(r: dict, h: dict) -> tuple[float | None, float | None]:
    """(última referência, recorde) considerando a busca completa e o que o vigia já avisou depois dela."""
    ult = h["execucoes"][-1]["melhor"] if h.get("execucoes") else None
    rec = h.get("recorde", {}).get("preco")
    al = est.get("rapida", {}).get(r["nome"], {}).get("alertou")
    if al and al.get("quando", "") > h.get("ultima_iso", ""):
        ult = min(x for x in (ult, al["preco"]) if x)
        rec = min(x for x in (rec, al["preco"]) if x)
    return ult, rec


def cal_atual(r: dict) -> dict:
    """Calendário mais recente: o da busca completa, atualizado pela checagem rápida."""
    h = hist.get(r["nome"], {})
    cal = {k: {"preco": v} for k, v in (h.get("ultimo_cal") or {}).items() if k > HOJE.isoformat()}
    rap = est.get("rapida", {}).get(r["nome"], {})
    if rap.get("quando", "") > h.get("ultima_iso", ""):
        for k, v in (rap.get("precos") or {}).items():
            if k in cal: cal[k] = {"preco": v}
    return cal


def link_dia(r: dict, dia: str) -> str:
    n = int(r.get("noites") or 0)
    return fontes.url_google(r["origem"], r["destino"], dia, A.mais(dia, n) if n else None)


# ---------------------------------------------------------------- 1. checagem rápida
def agrupar(dias: list[str], folga=5, maximo=4) -> list[tuple[str, str]]:
    dias = sorted(dias)
    grupos = []
    for k in dias:
        if grupos and (A.d(k) - A.d(grupos[-1][-1])).days <= folga:
            grupos[-1].append(k)
        else:
            grupos.append([k])
    while len(grupos) > maximo:  # junta os dois grupos mais próximos
        i = min(range(len(grupos) - 1), key=lambda j: (A.d(grupos[j + 1][0]) - A.d(grupos[j][-1])).days)
        grupos[i:i + 2] = [grupos[i] + grupos[i + 1]]
    return [(g[0], g[-1]) for g in grupos]


def checagem_rapida():
    if AV.get("checagem_rapida") is False:
        return
    intervalo = float(AV.get("rapida_horas", 2)) * 60 - 10
    if not TUDO and minutos_desde("rapida_t") < intervalo:
        return
    uso = est.get("apify")
    if uso and uso.get("pct", 0) >= 0.85:
        print("checagem rápida pausada: crédito da Apify acima de 85%"); return
    est["rapida_t"] = iso(AGORA)
    for _, r in ativas():
        h = hist.get(r["nome"], {})
        cal = cal_atual(r)
        if not cal or not APIFY:
            continue
        top = sorted(cal, key=lambda k: cal[k]["preco"])[:8]
        novos = {}
        try:
            for ini, fim in agrupar(top):
                novos.update(fontes.calendario(r["origem"], r["destino"], ini, fim, r.get("adultos", 1), int(r.get("noites") or 0) or None, APIFY))
        except fontes.ErroFonte as e:
            print("rápida:", r["nome"], e); continue
        if not novos:
            continue
        rap = est.setdefault("rapida", {}).setdefault(r["nome"], {})
        rap.update(quando=iso(AGORA), precos={k: v["preco"] for k, v in novos.items()})
        for k, v in novos.items():
            cal[k] = {"preco": v["preco"]}
        dia, info = min(novos.items(), key=lambda kv: kv[1]["preco"])
        p = info["preco"]
        ult, rec = preco_ref(r, h)
        print(f"⚡ {r['nome']}: {A.reais(p)} em {dia} (ref {ult}, recorde {rec})")
        motivos = []
        alvo = r.get("preco_alvo")
        if alvo and p <= alvo and not h.get("avisou_alvo") and not (ult and ult <= alvo):
            motivos.append(f"🎯 Abaixo do seu alvo de {A.reais(alvo)}")
        if rec and p < rec:
            motivos.append(f"🏆 Menor preço já visto (antes {A.reais(rec)})")
        elif ult and p <= ult * (1 - r.get("queda_minima", 5) / 100):
            motivos.append(f"📉 Caiu {round((1 - p / ult) * 100)}% desde a última olhada ({A.reais(ult)})")
        v = I.veredito(p, cal, h, r)
        if not motivos and v["nivel"] == "promo" and p not in (h.get("promo_avisada"), rap.get("promo_avisada")):
            motivos.append(f"🔥 Promoção forte: {round(v['desconto'] * 100)}% abaixo do normal")
        if not motivos:
            continue
        if v["nivel"] == "promo": rap["promo_avisada"] = p
        rap["alertou"] = {"preco": p, "dia": dia, "quando": iso(AGORA)}
        outros = sorted((x for x in novos.items() if x[0] != dia), key=lambda kv: kv[1]["preco"])[:3]
        texto = (f"⚡ <b>Checagem rápida</b> · {r['nome']}\n<b>{A.reais(p)}</b> saindo <b>{A.br(dia)}</b>\n" + "\n".join(motivos)
                 + f"\n\n{v['emoji']} <b>{v['rotulo']}</b> — {v['conselho']}\n<i>{' · '.join(v['detalhes'])}</i>")
        if outros:
            texto += "\n\nOutros dias agora: " + " · ".join(f"{A.d(k).strftime('%d/%m')} {A.reais(x['preco'])}" for k, x in outros)
        botoes = [[(f"🔎 Abrir {A.br(dia)} no Google Voos", info.get("url") or link_dia(r, dia))],
                  [(f"🔁 {t}", u) for t, u in I.links_comparar(r["origem"], r["destino"], dia, int(r.get("noites") or 0), r.get("adultos", 1))]]
        enviar(texto, botoes, forte=I.forte(motivos, v))


# ---------------------------------------------------------------- 2. promoções dos blogs
def vigiar_promos():
    if AV.get("promos") is False or not ativas():
        return
    if not TUDO and minutos_desde("promos_t") < 25:
        return
    est["promos_t"] = iso(AGORA)
    extras = AV.get("palavras_promo") or []
    if isinstance(extras, str): extras = [x.strip() for x in extras.split(",")]
    achados, erros = promos.buscar([r for _, r in ativas()], extras)
    for e in erros: print("promo:", e)
    vistos = est.setdefault("promos_vistos", [])
    primeira_vez = not vistos and not est.get("promos_iniciado")
    est["promos_iniciado"] = True
    novos, titulos = [], set()
    for p in achados:
        chave = promos.sem_acento(p["titulo"])[:60]
        if p["link"] in vistos or chave in titulos or chave in est.get("promos_titulos", []):
            continue
        titulos.add(chave); novos.append(p)
    est["promos_titulos"] = (est.get("promos_titulos", []) + sorted(titulos))[-300:]
    for p in achados:
        if p["link"] not in vistos: vistos.append(p["link"])
    est["promos_vistos"] = vistos[-400:]
    if primeira_vez:  # não despeja o arquivo todo: só o que saiu nas últimas 12 h
        novos = [p for p in novos if p["quando"] and AGORA - p["quando"] < timedelta(hours=12)]
    recentes = est.setdefault("promos_recentes", [])
    for p in sorted(novos, key=lambda x: not x["estrela"])[:5]:
        recentes.insert(0, {"titulo": p["titulo"], "link": p["link"], "fonte": p["fonte"], "quando": iso(p["quando"] or AGORA)})
        texto = (f"🏷️ <b>Promoção no {p['fonte']}</b>{' ⭐' if p['estrela'] else ''}\n<b>{p['titulo']}</b>\n"
                 f"Interessa: {', '.join(p['rotas'])}" + (f"\nPreço citado: {p['preco']}" if p.get("preco") else "")
                 + "\n<i>Promoção de blog costuma durar poucas horas: confira as datas lá.</i>")
        enviar(texto, [[("Abrir a promoção", p["link"])]], forte=p["estrela"])
    est["promos_recentes"] = recentes[:15]


# ---------------------------------------------------------------- 3. rede de segurança pós-compra
def vigiar_compras():
    compras = est.get("compras", [])
    restantes = []
    for c in compras:
        r = next((x for x in cfg["rotas"] if x["nome"] == c["rota"]), None)
        if not r:
            continue
        if AGORA >= de_iso(c["ate"]):
            enviar(f"⏱️ Acabou o prazo de 24 h da compra de <b>{c['rota']}</b> ({A.br(c['dia'])}, {A.reais(c['preco'])}). "
                   f"{'Não achei preço menor: você comprou bem! 👏' if not c.get('menor_avisado') else 'Espero que tenha aproveitado a queda.'}\n"
                   f"Se não precisa mais vigiar essa rota: /pausar {cfg['rotas'].index(r) + 1}")
            continue
        restantes.append(c)
        if not TUDO and c.get("checado") and (AGORA - de_iso(c["checado"])).total_seconds() < 55 * 60:
            continue
        c["checado"] = iso(AGORA)
        try:
            cal = fontes.calendario(r["origem"], r["destino"], c["dia"], c["dia"], r.get("adultos", 1), int(r.get("noites") or 0) or None, APIFY)
        except fontes.ErroFonte as e:
            print("compra:", e); continue
        if c["dia"] not in cal:
            continue
        p = cal[c["dia"]]["preco"]
        limite = c["preco"] - max(30, c["preco"] * 0.03)
        if p <= limite and p < c.get("menor_avisado", 1e12):
            c["menor_avisado"] = p
            pode = (A.d(c["dia"]) - A.d(c["criado"][:10])).days >= 7
            texto = (f"🛟 <b>Caiu depois que você comprou!</b>\n{c['rota']} · {A.br(c['dia'])}\n"
                     f"Agora: <b>{A.reais(p)}</b> · você pagou {A.reais(c['preco'])} → <b>economia de {A.reais(c['preco'] - p)}</b>\n\n"
                     + ("Pela regra da ANAC, dá pra desistir <b>sem custo</b> até " + hora_br(c["ate"]) + " (compra feita com 7+ dias de antecedência). "
                        "Compre a nova primeiro, depois cancele a antiga no site da cia." if pode else
                        "⚠️ A compra foi a menos de 7 dias do voo: a desistência grátis da ANAC não vale. Veja a regra de reembolso da tarifa."))
            enviar(texto, [[("🔎 Ver no Google Voos", cal[c["dia"]]["url"])]], forte=True)
    est["compras"] = restantes


# ---------------------------------------------------------------- 4. saúde do monitor e créditos
def horarios_agendados() -> list[tuple[int, int]]:
    try:
        return [(int(h), int(m)) for m, h in re.findall(r'cron:\s*"(\d+)\s+(\d+)\s+\*\s+\*\s+\*"', WF.read_text())]
    except OSError:
        return []


def saude():
    ultima = hist.get("_meta", {}).get("ultima")
    ult_dt = de_iso(ultima) if ultima else None
    # a. o GitHub pulou a busca agendada? dispara de novo
    for h, m in horarios_agendados():
        for dias_atras in (0, 1):
            alvo = datetime.combine(AGORA.date() - timedelta(days=dias_atras), datetime.min.time(), timezone.utc).replace(hour=h, minute=m)
            if timedelta(minutes=35) <= AGORA - alvo <= timedelta(hours=5) and (not ult_dt or ult_dt < alvo):
                if est.get("redisparo") == iso(alvo) or busca_rodando():
                    continue
                try:
                    disparar_busca(False)
                    est["redisparo"] = iso(alvo)
                    print("busca agendada não rodou: disparei de novo")
                except Exception as e:
                    print("redisparo falhou:", e)
    # b. parado há muito tempo
    if ult_dt and AGORA - ult_dt > timedelta(hours=30) and est.get("aviso_parado") != ultima:
        est["aviso_parado"] = ultima
        enviar(f"🩺 O monitor não completa uma busca desde {hora_br(ultima)}. Veja a aba Actions do repositório (algum erro de token?).", forte=True)
    # c. erros da última busca (token recusado, crédito acabou…)
    erros = hist.get("_meta", {}).get("erros") or []
    if erros and est.get("aviso_erros") != erros:
        est["aviso_erros"] = erros
        enviar("⚠️ A última busca teve problema:\n• " + "\n• ".join(erros[:5]), forte=True)
    # d. créditos (a cada 6 h)
    if TUDO or minutos_desde("creditos_t") > 360:
        est["creditos_t"] = iso(AGORA)
        uso = fontes.apify_uso(APIFY)
        if uso:
            est["apify"] = uso
            nivel = "95" if uso["pct"] >= 0.95 else "80" if uso["pct"] >= 0.8 else None
            chave = f"{HOJE:%Y-%m}-{nivel}"
            if nivel and est.get("aviso_apify") != chave:
                est["aviso_apify"] = chave
                enviar(f"💳 Apify: já usou US$ {uso['usado']:.2f} de US$ {uso['limite']:.2f} grátis deste mês ({uso['pct']:.0%}). "
                       + ("A checagem rápida fica pausada até o mês virar." if uso["pct"] >= 0.85 else "Se passar de 85%, pauso a checagem rápida sozinho."), forte=True)
        sr = fontes.serp_restante(SERP)
        if sr is not None:
            est["serp_restante"] = sr
            if sr < 15 and est.get("aviso_serp") != f"{HOJE:%Y-%m}":
                est["aviso_serp"] = f"{HOJE:%Y-%m}"
                enviar(f"💳 SerpAPI: restam só {sr} buscas neste mês. Os horários dos voos e a opinião do Google podem faltar nos avisos.")


# ---------------------------------------------------------------- 5. comandos do Telegram
AJUDA = """<b>Comandos do QuackVoo</b> 🦆
/status — preços, recorde e créditos
/rotas — suas rotas (com número)
/agora — busca completa agora
/buscar MAO VVI 29/05 [05/06] — preço de uma data
/calendario 1 [06/2027] — dias baratos 🟩🟨🟥
/grafico 1 — evolução do preço
/promos — últimas promoções achadas
/alvo 1 1800 — muda o preço-alvo
/pausar 1 · /ativar 1 — liga/desliga a rota
/nova MAO VVI 01/06/2027 30/06/2027 [noites] — cria rota
/apagar 1 sim — apaga a rota
/comprei 1 1172 29/05 — vigia 24 h pra ver se cai mais
<i>Se tiver só uma rota, o número é opcional. Respondo em ~1 min (com o Worker da Cloudflare) ou até ~15 min sem ele.</i>"""
COMANDOS_MENU = [("status", "Preços, recorde e créditos"), ("agora", "Busca completa agora"), ("buscar", "Preço de uma data: MAO VVI 29/05"),
                 ("calendario", "Dias baratos do mês"), ("grafico", "Evolução do preço"), ("promos", "Últimas promoções"),
                 ("rotas", "Suas rotas"), ("alvo", "Muda o preço-alvo"), ("pausar", "Pausa uma rota"), ("ativar", "Reativa uma rota"),
                 ("nova", "Cria rota: MAO VVI 01/06/2027 30/06/2027"), ("comprei", "Vigia 24 h depois da compra"), ("ajuda", "Todos os comandos")]


def data_arg(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", s)
    if not m:
        raise ValueError(f"não entendi a data “{s}” (use 29/05 ou 29/05/2027)")
    d, mth, a = int(m.group(1)), int(m.group(2)), m.group(3)
    if a:
        ano = int(a) + (2000 if len(a) == 2 else 0)
    else:
        ano = HOJE.year if date(HOJE.year, mth, d) >= HOJE else HOJE.year + 1
    return date(ano, mth, d).isoformat()


def preco_arg(s: str) -> float:
    s = s.replace("R$", "").strip()
    if "," in s: s = s.replace(".", "").replace(",", ".")
    else: s = s.replace(".", "")
    return float(s)


def rota_arg(args: list[str]) -> tuple[int, dict, list[str]]:
    """Primeiro argumento é o número da rota; se só existe uma rota, pode faltar."""
    n = len(cfg["rotas"])
    if not n:
        raise ValueError("você ainda não tem rotas: use /nova")
    if args and args[0].isdigit() and 1 <= int(args[0]) <= n:
        return int(args[0]), cfg["rotas"][int(args[0]) - 1], args[1:]
    if n == 1:
        return 1, cfg["rotas"][0], args
    if args and args[0].isdigit() and int(args[0]) <= 50:
        raise ValueError(f"não tenho a rota {args[0]}: você tem {n} (veja /rotas)")
    raise ValueError(f"diga o número da rota, de 1 a {n} (veja /rotas)")


def resumo_rota(i: int, r: dict) -> str:
    h = hist.get(r["nome"], {})
    tipo = f"ida e volta, {r['noites']} noites" if r.get("noites") else "só ida"
    linha = f"<b>{i}. {r['nome']}</b>{' ⏸️ pausada' if r.get('ativa') is False else ''}\n{r['origem']}→{r['destino']} · {tipo} · {A.br(str(r['ida_entre'][0]))} a {A.br(str(r['ida_entre'][1]))}"
    if r.get("preco_alvo"): linha += f" · alvo {A.reais(r['preco_alvo'])}"
    cal = cal_atual(r)
    if cal:
        dia = min(cal, key=lambda k: cal[k]["preco"]); p = cal[dia]["preco"]
        v = I.veredito(p, cal, h, r)
        linha += f"\nAgora: <b>{A.reais(p)}</b> em {A.br(dia)} · {v['emoji']} {v['rotulo']}"
    if h.get("recorde"):
        linha += f"\nRecorde: {A.reais(h['recorde']['preco'])} (visto {A.d(h['recorde']['visto']).strftime('%d/%m')})"
    return linha


def salvar_rotas():
    global mudou_rotas
    mudou_rotas = True
    ROTAS.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def cmd(texto: str) -> None:
    partes = texto.strip().split()
    c = partes[0].split("@")[0].lower().lstrip("/")
    args = partes[1:]
    try:
        if c in ("start", "ajuda", "help"):
            enviar(AJUDA)
        elif c == "status":
            blocos = "\n\n".join(resumo_rota(i, r) for i, r in enumerate(cfg["rotas"], 1)) or "Nenhuma rota ainda. Use /nova."
            info = []
            meta = hist.get("_meta", {})
            if meta.get("ultima"): info.append(f"🕐 Última busca completa: {hora_br(meta['ultima'])}")
            hs = horarios_agendados()
            if hs: info.append("📅 Buscas completas: " + " e ".join(f"{(h - 3) % 24:02d}:{m:02d}" for h, m in hs)
                               + (f" · checagem rápida a cada {AV.get('rapida_horas', 2)} h" if AV.get("checagem_rapida") is not False else ""))
            if est.get("apify"): info.append(f"💳 Apify: US$ {est['apify']['usado']:.2f} de {est['apify']['limite']:.0f} ({est['apify']['pct']:.0%})")
            if est.get("serp_restante") is not None: info.append(f"💳 SerpAPI: {est['serp_restante']} buscas restantes")
            for cpr in est.get("compras", []):
                info.append(f"🛟 Vigiando compra: {cpr['rota']} {A.br(cpr['dia'])} {A.reais(cpr['preco'])} até {hora_br(cpr['ate'])}")
            enviar(blocos + ("\n\n" + "\n".join(info) if info else ""))
        elif c == "rotas":
            enviar("\n\n".join(resumo_rota(i, r) for i, r in enumerate(cfg["rotas"], 1)) or "Nenhuma rota. Use /nova.")
        elif c == "agora":
            if busca_rodando():
                enviar("🔎 Já tem uma busca rodando: o relatório chega em poucos minutos.")
            else:
                disparar_busca(True)
                enviar("🔎 Buscando agora! O relatório completo chega em ~3–5 min.")
        elif c in ("pausar", "ativar"):
            i, r, _ = rota_arg(args)
            r["ativa"] = c == "ativar"
            salvar_rotas()
            enviar(f"{'▶️ Reativei' if c == 'ativar' else '⏸️ Pausei'} a rota {i}: {r['nome']}.")
        elif c == "alvo":
            i, r, resto = rota_arg(args)
            if not resto: raise ValueError("diga o valor: /alvo 1 1800")
            r["preco_alvo"] = round(preco_arg(resto[0]))
            salvar_rotas()
            enviar(f"🎯 Alvo da rota {i} agora é {A.reais(r['preco_alvo'])}. Te aviso quando chegar lá.")
        elif c == "nova":
            if len(args) < 4: raise ValueError("use: /nova MAO VVI 01/06/2027 30/06/2027 [noites]")
            o, dst = args[0].upper(), args[1].upper()
            ini, fim = data_arg(args[2]), data_arg(args[3])
            if fim < ini: raise ValueError("a data final vem antes da inicial")
            noites = int(args[4]) if len(args) > 4 else 0
            nova = {"nome": f"{nome_aero(o)} -> {nome_aero(dst)} ({A.d(ini).strftime('%m/%y')})",
                    "origem": o, "destino": dst, "ida_entre": [ini, fim], "noites": noites, "adultos": 1,
                    "queda_minima": 5, "conexoes": [x for x in ["GRU", "BSB"] if x not in (o, dst)], "conexao_dias": [0, 1]}
            if any(x["nome"] == nova["nome"] for x in cfg["rotas"]): nova["nome"] += f" #{len(cfg['rotas']) + 1}"
            cfg["rotas"].append(nova)
            salvar_rotas()
            enviar(f"✅ Rota {len(cfg['rotas'])} criada: <b>{nova['nome']}</b> ({A.br(ini)} a {A.br(fim)}, {'só ida' if not noites else f'{noites} noites'}).\n"
                   f"A primeira olhada vem na próxima busca completa (ou mande /agora). Ajuste alvo e escalas no painel ou com /alvo {len(cfg['rotas'])} 1500.")
        elif c == "apagar":
            i, r, resto = rota_arg(args)
            if not resto or resto[0].lower() != "sim":
                enviar(f"Tem certeza? Pra apagar <b>{r['nome']}</b> mande: /apagar {i} sim")
            else:
                cfg["rotas"].pop(i - 1); salvar_rotas()
                enviar(f"🗑️ Apaguei a rota {i}: {r['nome']}.")
        elif c == "buscar":
            if len(args) < 3: raise ValueError("use: /buscar MAO VVI 29/05 [volta 05/06]")
            o, dst, ida = args[0].upper(), args[1].upper(), data_arg(args[2])
            volta = data_arg(args[3]) if len(args) > 3 else None
            v = fontes.detalhes_voo(o, dst, ida, 1, SERP, volta)
            if not v or not v.get("preco"):
                enviar(f"Não achei voos {o}→{dst} em {A.br(ida)}." + ("" if SERP else " (falta a SerpAPI)")); return
            g = v.get("google", {})
            txt = (f"🔎 <b>{o}→{dst}</b> {A.br(ida)}" + (f" ↩ {A.br(volta)}" if volta else " (só ida)") + f"\n<b>{A.reais(v['preco'])}</b> · {v['cia']}\n"
                   f"sai {v['saida'][-5:]} · chega {v['chegada'][-5:]} · " + ("direto" if not v["paradas"] else f"{v['paradas']} parada(s)"))
            if g.get("faixa"): txt += f"\nGoogle: normal é {A.reais(g['faixa'][0])}–{A.reais(g['faixa'][1])}"
            if g.get("nivel"): txt += " · este está " + {"low": "🟢 BAIXO", "typical": "🟡 típico", "high": "🔴 ALTO"}.get(g["nivel"], g["nivel"])
            enviar(txt, [[("Abrir no Google Voos", v["url"])], [(t, u) for t, u in I.links_comparar(o, dst, ida, (A.d(volta) - A.d(ida)).days if volta else 0, 1)]])
        elif c == "calendario":
            i, r, resto = rota_arg(args)
            mes = None
            if resto:
                m = re.fullmatch(r"(\d{1,2})/(\d{2,4})", resto[0])
                if m: mes = f"{int(m.group(2)) + (2000 if len(m.group(2)) == 2 else 0)}-{int(m.group(1)):02d}"
            cal = cal_atual(r)
            enviar(f"📅 <b>{r['nome']}</b>\n\n" + I.texto_calor(cal, mes))
        elif c == "grafico":
            i, r, _ = rota_arg(args)
            url = I.url_grafico(hist.get(r["nome"], {}), r["nome"])
            if not url: enviar("Ainda não tenho buscas suficientes pra desenhar o gráfico."); return
            avisos.foto_url(url, f"📈 <b>{r['nome']}</b>: menor preço a cada busca", silencioso=True)
        elif c == "promos":
            rec = est.get("promos_recentes", [])
            enviar("🏷️ <b>Últimas promoções que achei</b>\n" + ("\n".join(f"• <a href=\"{p['link']}\">{p['titulo']}</a> ({p['fonte']}, {hora_br(p['quando'])})" for p in rec[:8])
                                                           or "Nenhuma ainda pros seus destinos."))
        elif c == "comprei":
            i, r, resto = rota_arg(args)
            if not resto: raise ValueError("use: /comprei 1 1172 29/05")
            preco = preco_arg(resto[0])
            cal = cal_atual(r)
            dia = data_arg(resto[1]) if len(resto) > 1 else (min(cal, key=lambda k: cal[k]["preco"]) if cal else None)
            if not dia: raise ValueError("diga a data do voo: /comprei 1 1172 29/05")
            est.setdefault("compras", []).append({"rota": r["nome"], "preco": preco, "dia": dia, "criado": iso(AGORA), "ate": iso(AGORA + timedelta(hours=24))})
            enviar(f"🛟 Anotado: {r['nome']} em {A.br(dia)} por {A.reais(preco)}.\nVou checar de hora em hora até {hora_br(iso(AGORA + timedelta(hours=24)))}: "
                   "se cair, te aviso pra recomprar e desistir da antiga sem custo (regra da ANAC, compra com 7+ dias de antecedência).\n"
                   f"Quer parar de vigiar a rota? /pausar {i}")
        else:
            enviar("Não conheço esse comando. Mande /ajuda.")
    except Exception as e:
        enviar(f"⚠️ {e}")


def comandos():
    if est.get("comandos_v") != VERSAO_COMANDOS:
        try:
            avisos.tg("setMyCommands", {"commands": [{"command": a, "description": b} for a, b in COMANDOS_MENU]})
            est["comandos_v"] = VERSAO_COMANDOS
        except Exception as e:
            print("menu de comandos:", e)
    try:
        r = avisos.tg("getUpdates", {"offset": est.get("tg_offset", 0), "timeout": 0, "allowed_updates": ["message"]})
    except Exception as e:
        if "409" in str(e): return  # o Worker da Cloudflare já recebe os comandos na hora
        print("getUpdates:", e); return
    for u in r.get("result", []):
        est["tg_offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        if str(m.get("chat", {}).get("id")) != CHAT:
            continue  # só obedece ao seu chat
        t = (m.get("text") or "").strip()
        if t.startswith("/"):
            print("comando:", t)
            cmd(t)


# ---------------------------------------------------------------- principal
def comando_do_worker() -> bool:
    """Comando que chegou pelo Worker da Cloudflare (resposta rápida). Só obedece ao seu chat."""
    bruto = os.getenv("COMANDO", "").strip()
    if not bruto:
        return False
    try:
        d = json.loads(bruto)
    except ValueError:
        return True
    if str(d.get("chat")) == CHAT and str(d.get("texto", "")).startswith("/"):
        print("comando (worker):", d["texto"])
        cmd(d["texto"])
    return True


def main():
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        sys.exit("Falta TELEGRAM_BOT_TOKEN.")
    if comando_do_worker():  # rodada curta: só responde o comando
        tarefas = []
    else:
        tarefas = [("comandos", comandos), ("saúde", saude), ("compras", vigiar_compras),
                   ("promoções", vigiar_promos), ("checagem rápida", checagem_rapida), ("comandos", comandos)]
    for nome, tarefa in tarefas:
        try:
            tarefa()
        except Exception as e:
            print(f"{nome} falhou:", e)
    VIGIA.parent.mkdir(exist_ok=True)
    VIGIA.write_text(json.dumps(est, ensure_ascii=False, indent=1, default=str))
    if mudou_rotas: print("rotas.yaml alterado por comando")


if __name__ == "__main__":
    main()
