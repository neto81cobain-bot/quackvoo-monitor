"""Passagens de barco e lancha na Amazônia, de duas plataformas de venda online:
  • Yjara Viagens (Pará e Baixo Amazonas: Santarém, Oriximiná, Trombetas, Óbidos, Juruti, Parintins, Manaus…)
  • Navegam (Amazonas: Manaus, Parintins, Faro, Nhamundá, Terra Santa, Solimões…)
Lê a mesma busca pública que os sites usam, sem login. Volume baixo: só os trechos que você vigia e os /barco que você pede.
As viagens com escala aparecem: cada pedaço da viagem é vendido como um trecho (ex.: Manaus → Oriximiná passando por Juruti)."""
import re
from datetime import date, datetime, timedelta, timezone

import requests

from aeroportos import sem_acento

SITE = "https://yjaraviagens.com"
API = "https://app.techrios.online/api"
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Accept": "application/json", "Accept-Language": "pt-BR,pt;q=0.9"}
APELIDOS = {"stm": "santarem", "trombetas": "trombetas", "porto trombetas": "trombetas", "terra santa": "terra-santa",
            "mao": "manaus", "bel": "belem", "orx": "oriximina", "obidos": "obidos"}
_CHAVE: dict = {}


NOMES = {"oriximina": "Oriximiná", "santarem": "Santarém", "terra-santa": "Terra Santa", "obidos": "Óbidos", "belem": "Belém",
         "alter-do-chao": "Alter do Chão", "macapa": "Macapá", "maues": "Maués", "curua": "Curuá", "gurupa": "Gurupá",
         "nhamunda": "Nhamundá", "urucara": "Urucará", "trombetas": "Porto Trombetas", "monte-alegre": "Monte Alegre"}


def nome(sl: str) -> str:
    return NOMES.get(sl, sl.replace("-", " ").title())


class ErroBarco(Exception):
    pass


WA_YJARA, WA_NAVEGAM = "5593991893803", "5592988552157"


def wa(n) -> str:
    d = re.sub(r"\D", "", str(n or ""))
    if not d:
        return ""
    return "https://wa.me/" + ("55" + d if len(d) <= 11 else d)


def slug(cidade: str) -> str:
    s = sem_acento(cidade).strip().replace("/pa", "").replace("/am", "").replace("/ap", "")
    s = APELIDOS.get(s, s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _chave() -> str:
    """A chave pública que o próprio site usa no navegador (lida do site a cada execução, não fica guardada)."""
    if _CHAVE.get("v"):
        return _CHAVE["v"]
    h = requests.get(SITE + "/", headers=UA, timeout=30).text
    m = re.search(r'src="(/assets/main-[^"]+\.js)"', h)
    if not m:
        raise ErroBarco("não achei o script do site da Yjara (o site mudou?)")
    js = requests.get(SITE + m.group(1), headers=UA, timeout=40).text
    k = re.search(r'getAppApiToken\(\)\{return"([^"]+)"', js)
    if not k:
        raise ErroBarco("o site da Yjara mudou a forma de buscar")
    _CHAVE["v"] = k.group(1)
    return _CHAVE["v"]


def link(o: str, d: str, dia: str) -> str:
    return f"{SITE}/escolher-passagem/{slug(o)}/{slug(d)}/somente-ida/{dia}"


def buscar(origem: str, destino: str, dia: str) -> list[dict]:
    """Saídas de um dia. dia = AAAA-MM-DD."""
    itens = []
    for pg in range(1, 9):  # a API pagina (às vezes 1 por página)
        p = {"origem": slug(origem), "destino": slug(destino), "data_hora": dia, "quantia": 1, "subdomain": "yjaraviagens",
             "intervalo": "", "empresa": "", "tipo_comodidade_id": "", "per_page": 50, "page": pg}
        try:
            r = requests.get(API + "/trechos-viagem", params=p, headers={**UA, "X-API-KEY": _chave()}, timeout=30)
            j = r.json()
        except (requests.RequestException, ValueError) as e:
            raise ErroBarco(f"Yjara não respondeu ({str(e)[:60]})")
        if not j.get("success"):
            raise ErroBarco(str(j.get("message", "erro"))[:100])
        t = j["data"]["trechos"]
        itens += t.get("data") or []
        if pg >= (t.get("last_page") or 1):
            break
    out = []
    for x in itens:
        emp = x.get("empresa") or {}
        saida = x.get("data_embarque") or x.get("saida")
        out.append({
            "id": x.get("id_viagem") or x.get("id"), "embarcacao": re.sub(r"\s*-\s*(Lancha|Navio|Barco|Ferry.*)$", "", x.get("embarcacao", "")).strip(),
            "tipo": x.get("tipo_embarcacao") or "", "empresa": (emp.get("nome_fantasia") or emp.get("xnome") or "").strip(),
            "trecho": x.get("trecho", ""), "horario": x.get("horario", ""), "saida": saida, "duracao": x.get("tempo_viagem"),
            "preco": float(x.get("valor_num") or 0), "desconto": x.get("desconto"), "url": link(origem, destino, dia)})
    return sorted(out, key=lambda v: (v["horario"][6:10] + v["horario"][3:5] + v["horario"][:2] + v["horario"][11:], v["preco"]))


def paradas_yjara(origem: str, dia: str) -> dict:
    """Todos os trechos vendidos saindo de `origem` no dia, agrupados por viagem: {id_viagem: [(destino, preço)]}."""
    out = {}
    for pg in range(1, 9):
        p = {"origem": slug(origem), "destino": "", "data_hora": dia, "quantia": 1, "subdomain": "yjaraviagens", "per_page": 50, "page": pg}
        try:
            j = requests.get(API + "/trechos-viagem", params=p, headers={**UA, "X-API-KEY": _chave()}, timeout=30).json()
            dd = j["data"]["trechos"]
        except Exception:
            break
        for x in dd["data"]:
            out.setdefault(str(x.get("id_viagem")), []).append((x["trecho"].split(" x ")[-1].split("/")[0], float(x.get("valor_num") or 0)))
        if pg >= (dd.get("last_page") or 1):
            break
    return out


# ---------------------------------------------------------------- Navegam
NAVEGAM = "https://navegam-fluvial-api-prod-979984919366.us-central1.run.app"
_CIDADES_NAV: dict = {}


def _cidades_navegam() -> dict:
    if not _CIDADES_NAV:
        for pg in range(1, 5):
            try:
                j = requests.get(NAVEGAM + "/ecommerce/popular-destinations", params={"page": pg, "page_size": 50}, headers=UA, timeout=30).json()
            except Exception:
                break
            dd = (j.get("result") or {}).get("data", [])
            for x in dd:
                _CIDADES_NAV.setdefault(slug(x["name"]), x["id"])
            if len(dd) < 50:
                break
    return _CIDADES_NAV


def navegam(origem: str, destino: str, inicio: date, dias: int) -> dict[str, list[dict]]:
    cid = _cidades_navegam()
    o, d = cid.get(slug(origem)), cid.get(slug(destino))
    if not (o and d):
        return {}
    fim = inicio + timedelta(days=dias - 1)
    out = {}
    for pg in range(1, 8):
        try:
            j = requests.get(NAVEGAM + "/ecommerce/travels", params={"origin_id": o, "destination_id": d, "page": pg},
                             headers=UA, timeout=30).json()  # 10 por página, em ordem de data
        except Exception:
            break
        dd = (j.get("result") or {}).get("data", [])
        for x in dd:
            sai = datetime.fromisoformat(x["departure_date"].replace("Z", "+00:00"))
            if not (inicio <= sai.date() <= fim):
                continue
            dia = sai.date().isoformat()
            dur = ""
            try:
                h = (datetime.fromisoformat(x["arrival_date"].replace("Z", "+00:00")) - sai).total_seconds() / 3600
                dur = f"{int(h)}:{int(round((h % 1) * 60)):02d}"
            except Exception:
                pass
            comida = x.get("feeding_cost") or 0
            out.setdefault(dia, []).append({
                "id": f"nav{x['id']}", "embarcacao": (x.get("boat") or {}).get("name", ""), "tipo": (x.get("boat") or {}).get("type", ""),
                "empresa": "Navegam", "trecho": f"{x['origin']['name']} x {x['destination']['name']}",
                "horario": sai.strftime("%d/%m/%Y %H:%M"), "saida": x["departure_date"], "duracao": dur,
                "preco": float(x.get("sale_cost") or x.get("transportation_cost") or 0), "comida": float(comida),
                "zap": wa(WA_NAVEGAM) if (x.get("boat") or {}).get("whatsapp_sale") is True else "",
                "url": f"https://navegam.com.br/busca?origem={o}&destino={d}&ida={dia}&type=ida&passageiros=1", "fonte": "Navegam"})
        if len(dd) < 10 or (dd and datetime.fromisoformat(dd[-1]["departure_date"].replace("Z", "+00:00")).date() > fim):
            break
    return out


def proximos(origem: str, destino: str, dias: int = 7, inicio: str | None = None, paradas: bool = False) -> dict[str, list[dict]]:
    """Saídas dos próximos dias nas duas plataformas. paradas=True: diz por onde a viagem passa antes (Yjara)."""
    d0 = date.fromisoformat(inicio) if inicio else date.today()
    out = {}
    erros = []
    for i in range(dias):
        dia = (d0 + timedelta(days=i)).isoformat()
        try:
            v = buscar(origem, destino, dia)
        except ErroBarco as e:
            erros.append(str(e)); v = []
        if v and paradas:
            grupos = paradas_yjara(origem, dia)
            for x in v:
                antes = sorted((p, n) for n, p in grupos.get(str(x["id"]), []) if p < x["preco"] and slug(n) != slug(destino))
                x["via"] = [n for _, n in antes]
        if v:
            out[dia] = v
    try:
        for dia, vs in navegam(origem, destino, d0, dias).items():
            out.setdefault(dia, []).extend(vs)
    except Exception as e:
        erros.append(f"Navegam: {str(e)[:60]}")
    if not out and erros and len(erros) >= dias:
        raise ErroBarco(erros[0])
    for dia in out:
        out[dia].sort(key=lambda v: v["horario"][11:])
    return dict(sorted(out.items()))


SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _rs(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").replace(",00", "")


def contatos(agenda, o: str, d: str) -> list[dict]:
    o, d = slug(o), slug(d)
    out = []
    for c in agenda or []:
        a, b = slug(c.get("de", "")), slug(c.get("para", "") or "")
        if {a, b} == {o, d} or (not b and a in (o, d)):
            out.append(c)
    return out


def _rodape(origem, destino, agenda) -> str:
    L = []
    ag = contatos(agenda, origem, destino)
    if ag:
        L += ["", "📒 <b>Também pergunte</b>"] + [f" {c['nome']} · <a href=\"{wa(c['whatsapp'])}\">WhatsApp</a>" for c in ag[:6]]
    L += ["", f"<i>Toque no preço pra comprar. Dúvida: <a href=\"{wa(WA_YJARA)}\">Yjara</a> · <a href=\"{wa(WA_NAVEGAM)}\">Navegam</a></i>"]
    return "\n".join(L)


def texto(origem: str, destino: str, saidas: dict[str, list[dict]], agenda=None) -> str:
    """Mensagem do Telegram: por dia, cada saída com lancha, empresa, horário e preço (o preço abre a compra)."""
    nome_o, nome_d = nome(slug(origem)), nome(slug(destino))
    if not saidas:
        return (f"🚤 <b>{nome_o} → {nome_d}</b>\nNão achei saídas à venda online nesses dias.\n"
                "<i>Procurei na Yjara e na Navegam. A venda online costuma abrir 5 dias antes; lancha pequena vende no porto ou pelo WhatsApp.</i>"
                + _rodape(origem, destino, agenda))
    todos = [v for vs in saidas.values() for v in vs]
    menor = min(todos, key=lambda v: v["preco"])
    L = [f"🚤 <b>{nome_o} → {nome_d}</b>", f"<i>{len(todos)} saídas · a partir de {_rs(menor['preco'])}</i>", ""]
    for dia, vs in saidas.items():
        d = date.fromisoformat(dia)
        L.append(f"<b>{SEMANA[d.weekday()]} {d:%d/%m}</b>")
        for v in vs:
            hora = v["horario"][-5:]
            extra = ""
            m = re.fullmatch(r"(\d{1,2})[:Hh](\d{2})", str(v.get("duracao") or ""))
            if m:
                extra = f" · ⏱ {int(m[1])}h" + (m[2] if m[2] != "00" else "")
            barato = " 💚" if v["preco"] == menor["preco"] else ""
            via = f"\n      <i>para antes em {', '.join(v['via'])}</i>" if v.get("via") else ""
            comida = f" (+{_rs(v['comida'])} comida)" if v.get("comida") else ""
            zap = f" · <a href=\"{v['zap']}\">WhatsApp</a>" if v.get("zap") else ""
            L.append(f"  {hora} · {v['embarcacao'] or v['tipo']} <i>({v['empresa'] or v['tipo']})</i> · "
                     f"<a href=\"{v['url']}\">{_rs(v['preco'])}</a>{comida}{barato}{extra}{zap}{via}")
        L.append("")
    return "\n".join(L).rstrip() + "\n" + _rodape(origem, destino, agenda)
