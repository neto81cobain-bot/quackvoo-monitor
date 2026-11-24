"""Passagens de barco e lancha na Amazônia (Yjara Viagens: plataforma autorizada pelas empresas que fazem as viagens).
Lê a mesma busca pública que o site usa, sem login. Volume baixo: só os trechos que você vigia e os /barco que você pede."""
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
    p = {"origem": slug(origem), "destino": slug(destino), "data_hora": dia, "quantia": 1, "subdomain": "yjaraviagens",
         "intervalo": "", "empresa": "", "tipo_comodidade_id": ""}
    try:
        r = requests.get(API + "/trechos-viagem", params=p, headers={**UA, "X-API-KEY": _chave()}, timeout=30)
        j = r.json()
    except (requests.RequestException, ValueError) as e:
        raise ErroBarco(f"Yjara não respondeu ({str(e)[:60]})")
    if not j.get("success"):
        raise ErroBarco(str(j.get("message", "erro"))[:100])
    out = []
    for x in j["data"]["trechos"]["data"]:
        emp = x.get("empresa") or {}
        saida = x.get("data_embarque") or x.get("saida")
        out.append({
            "id": x.get("id_viagem") or x.get("id"), "embarcacao": re.sub(r"\s*-\s*(Lancha|Navio|Barco|Ferry.*)$", "", x.get("embarcacao", "")).strip(),
            "tipo": x.get("tipo_embarcacao") or "", "empresa": (emp.get("nome_fantasia") or emp.get("xnome") or "").strip(),
            "trecho": x.get("trecho", ""), "horario": x.get("horario", ""), "saida": saida, "duracao": x.get("tempo_viagem"),
            "preco": float(x.get("valor_num") or 0), "desconto": x.get("desconto"), "url": link(origem, destino, dia)})
    return sorted(out, key=lambda v: (v["horario"][6:10] + v["horario"][3:5] + v["horario"][:2] + v["horario"][11:], v["preco"]))


def proximos(origem: str, destino: str, dias: int = 7, inicio: str | None = None) -> dict[str, list[dict]]:
    d0 = date.fromisoformat(inicio) if inicio else date.today()
    out = {}
    for i in range(dias):
        dia = (d0 + timedelta(days=i)).isoformat()
        v = buscar(origem, destino, dia)
        if v:
            out[dia] = v
    return out


SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _rs(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").replace(",00", "")


def texto(origem: str, destino: str, saidas: dict[str, list[dict]]) -> str:
    """Mensagem do Telegram: por dia, cada saída com lancha, empresa, horário e preço (o preço abre a compra)."""
    nome_o, nome_d = nome(slug(origem)), nome(slug(destino))
    if not saidas:
        return (f"🚤 <b>{nome_o} → {nome_d}</b>\nNão achei saídas à venda online nesses dias.\n"
                "<i>Algumas lanchas só vendem no porto ou pelas redes. A venda online abre, por regra da ANTAQ, pelo menos 5 dias antes.</i>")
    todos = [v for vs in saidas.values() for v in vs]
    menor = min(todos, key=lambda v: v["preco"])
    L = [f"🚤 <b>{nome_o} → {nome_d}</b>", f"<i>{len(todos)} saídas · a partir de {_rs(menor['preco'])}</i>", ""]
    for dia, vs in saidas.items():
        d = date.fromisoformat(dia)
        L.append(f"<b>{SEMANA[d.weekday()]} {d:%d/%m}</b>")
        for v in vs:
            hora = v["horario"][-5:]
            extra = f" · {v['duracao']}" if v.get("duracao") else ""
            barato = " 💚" if v["preco"] == menor["preco"] else ""
            L.append(f"  {hora} · {v['embarcacao'] or v['tipo']} <i>({v['empresa'] or v['tipo']})</i> · "
                     f"<a href=\"{v['url']}\">{_rs(v['preco'])}</a>{barato}{extra}")
        L.append("")
    L.append("<i>Toque no preço pra comprar na Yjara (PIX tem desconto). Lanchas que só vendem no porto ou nas redes não aparecem aqui.</i>")
    return "\n".join(L)
