"""Radar do Norte 🌴 — pra onde está barato voar saindo de Manaus, Belém, Santarém e Trombetas.

Usa a busca "Explorar" do Google Voos (pela biblioteca grátis Fli), guarda o preço de cada destino ao
longo dos dias e avisa quando um cair bem abaixo do normal. Domingo manda o resumo da semana.
"""
from datetime import date, timedelta
from statistics import median
from datetime import datetime

import analise as A
import fontes
import inteligencia as I
from aeroportos import nome as nome_aero

ORIGENS_PADRAO = ["MAO", "BEL", "STM", "TMT"]
OFFSETS = [10, 17, 24, 31, 38, 45, 52, 59, 66, 73, 80, 87]  # dias à frente, revezados a cada rodada


def _mais_horas(iso: str, h: int) -> str:
    return (datetime.fromisoformat(iso) + timedelta(hours=h)).isoformat()[:13]


def explorar(origem: str, data: str) -> list[dict]:
    """Destinos com o menor preço pra sair de `origem` em `data` (só ida)."""
    from fli.models import Airport, ExploreSearchFilters
    from fli.search.explore import SearchExplore
    try:
        f = ExploreSearchFilters(origin=getattr(Airport, origem), departure_date=data)
        res = SearchExplore().search(f, currency="BRL", language="pt-BR", country="BR")
    except Exception as e:
        print(f"radar {origem} {data}: {str(e)[:120]}")
        return []
    out = []
    for d in res.destinations:
        if d.price and d.destination_airport and d.destination_airport != origem:
            out.append({"dest": d.destination_airport, "cidade": d.name, "pais": d.country, "preco": round(d.price),
                        "data": d.departure_date or data, "cia": d.airline_name, "paradas": d.stops})
    return out


BRASIL = "/m/015fr"  # filtro "só destinos no Brasil" da Explorar


def explorar_serp(origem: str, chave: str, area: str | None = None) -> list[dict]:
    """Reserva paga (1 busca SerpAPI): 'Explorar' do Google pros próximos meses, datas flexíveis."""
    import requests
    if not chave:
        return []
    try:
        d = requests.get("https://serpapi.com/search.json", timeout=60, params={
            "engine": "google_travel_explore", "departure_id": origem, "currency": "BRL", "hl": "pt", "gl": "br", "api_key": chave,
            **({"arrival_area_id": area} if area else {})}).json()
    except Exception as e:
        print(f"radar serp {origem}: {e}"); return []
    if d.get("error"):
        print(f"radar serp {origem}: {d['error']}"); return []
    out = []
    for x in d.get("destinations") or []:
        ap = x.get("destination_airport") or x.get("airport") or {}
        cod = (ap.get("code") if isinstance(ap, dict) else ap) or x.get("airport_code")
        preco = x.get("flight_price") or x.get("price")
        ida = x.get("start_date") or x.get("outbound_date")
        if not (cod and preco and ida) or cod == origem:
            continue
        out.append({"dest": cod, "cidade": x.get("name") or cod, "pais": x.get("country"), "preco": round(preco), "data": ida,
                    "volta": x.get("end_date") or x.get("return_date"), "cia": x.get("airline"), "paradas": x.get("number_of_stops")})
    return out


def rodar(est: dict, origens: list[str], agora_iso: str, rodada: int, serp: str = "") -> list[dict]:
    """Uma varredura. Atualiza o histórico em `est` e devolve as ofertas que merecem aviso agora."""
    rad = est.setdefault("radar", {"hist": {}, "alertas": {}})
    hoje = date.today()
    offs = [OFFSETS[(rodada + k * 4) % len(OFFSETS)] for k in range(3)]
    boas = []
    coletas = []
    falhas = 0
    pula_gratis = rad.get("gratis_off_ate", "") > agora_iso  # o Google anda recusando a busca grátis
    for o in ([] if pula_gratis else origens):
        for off in offs:
            achou = explorar(o, (hoje + timedelta(days=off)).isoformat())
            coletas += [(o, x) for x in achou]
            falhas = 0 if achou else falhas + 1
            if falhas >= 2 and not coletas:
                break  # o Google está recusando: não insiste
        if falhas >= 2 and not coletas:
            break
    # o Google às vezes recusa a busca grátis; aí usa a SerpAPI, 1 aeroporto por vez, no máx. a cada 12 h
    sr = est.get("serp_restante")
    ult_serp = rad.get("serp_t", "")
    if not coletas and not pula_gratis:
        rad["gratis_off_ate"] = _mais_horas(agora_iso, 24) + ":00:00+00:00"
    if not coletas and serp and (sr is None or sr > 80) and (not ult_serp or agora_iso[:13] >= _mais_horas(ult_serp, 12)):
        pares = [(o, a) for o in origens for a in (None, BRASIL)]  # cada aeroporto: mundo e só Brasil, revezando
        o, area = pares[rad.get("serp_i", 0) % len(pares)]
        rad["serp_i"] = rad.get("serp_i", 0) + 1
        rad["serp_t"] = agora_iso
        coletas = [(o, x) for x in explorar_serp(o, serp, area)]
        print(f"radar: SerpAPI trouxe {len(coletas)} destinos saindo de {o} ({'Brasil' if area else 'mundo'})")
    for o, x in coletas:
        chave = f"{o}>{x['dest']}"
        h = rad["hist"].setdefault(chave, [])
        normal = median([p for _, _, p in h]) if len(h) >= 5 else None
        h.append([agora_iso[:10], x["data"], x["preco"]])
        rad["hist"][chave] = h[-60:]
        x.update(origem=o, normal=normal, chave=chave, visto=agora_iso)
        rad.setdefault("ultimos", {})[chave] = x
        if normal and x["preco"] <= 0.75 * normal:
            ja = rad["alertas"].get(chave)
            if not ja or x["preco"] <= ja["preco"] * 0.9 or (hoje - A.d(ja["quando"][:10])).days >= 7:
                rad["alertas"][chave] = {"preco": x["preco"], "quando": agora_iso}
                boas.append(x)
    # só o melhor dia por destino
    melhores = {}
    for x in boas:
        if x["chave"] not in melhores or x["preco"] < melhores[x["chave"]]["preco"]:
            melhores[x["chave"]] = x
    return sorted(melhores.values(), key=lambda x: x["preco"] / x["normal"])


def linha(x: dict, com_normal=True) -> str:
    url = fontes.url_google(x["origem"], x["dest"], x["data"], x.get("volta"))
    base = (f"<b>{nome_aero(x['origem'])} → {x['cidade']}</b> "
            f'<a href="{url.replace("&", "&amp;")}">{A.reais(x["preco"])}</a> · {A.SEMANA[A.d(x["data"]).weekday()]} {A.d(x["data"]).strftime("%d/%m")}')
    extra = []
    if com_normal and x.get("normal"):
        extra.append(f"{round((1 - x['preco'] / x['normal']) * 100)}% abaixo do normal ({A.reais(x['normal'])})")
    if x.get("cia"):
        extra.append(x["cia"] + (" · direto" if x.get("paradas") == 0 else ""))
    return base + (f"\n<i>{' · '.join(extra)}</i>" if extra else "")


def texto_alerta(boas: list[dict]) -> tuple[str, list]:
    L = ["🌴 <b>Radar do Norte: passagem boa saindo daqui!</b>", ""]
    for x in boas[:5]:
        L += [f"🔥 {linha(x)}", ""]
    L.append("<i>Preço com taxas" + (" (ida e volta quando há data de volta)" if any(x.get("volta") for x in boas) else ", só ida") + ". Promoção assim costuma durar pouco.</i>")
    x = boas[0]
    sites = I.links_sites(x["origem"], x["dest"], x["data"])
    botoes = [[(f"🔎 Ver {x['cidade']} no Google Voos", fontes.url_google(x["origem"], x["dest"], x["data"]))],
              [(n, u) for n, u, _ in sites["Buscadores"][1:3] + sites["Agências"][:1]]]
    return "\n".join(L), botoes


def texto_resumo(est: dict) -> str | None:
    """Domingo: os destinos mais em conta da semana (ou os mais abaixo do normal, quando já há histórico)."""
    limite = (date.today() - timedelta(days=7)).isoformat()
    ult = [x for x in (est.get("radar") or {}).get("ultimos", {}).values()
           if x.get("visto", "")[:10] >= limite and x["data"] > date.today().isoformat()]
    if not ult and not (est.get("oficiais") or {}).get("ultimas"):
        return None
    com_normal = [x for x in ult if x.get("normal")]
    if len(com_normal) >= 5:
        lista = sorted(com_normal, key=lambda x: x["preco"] / x["normal"])[:8]
        titulo = "os destinos mais abaixo do preço normal"
    else:
        lista = sorted(ult, key=lambda x: x["preco"])[:8]
        titulo = "os destinos mais baratos (ainda aprendendo o preço normal de cada um)"
    L = ["🌴 <b>Saindo do Norte esta semana</b>", f"<i>{titulo}</i>", ""]
    for x in lista:
        L += [f"• {linha(x)}"]
    of = [o for o in (est.get("oficiais") or {}).get("ultimas", {}).values()
          if o.get("visto", "")[:10] >= limite and o["ida"] > date.today().isoformat()]
    if of:
        import ofertas
        L += ["", "✈️ <b>Ofertas anunciadas pela GOL e pela Azul</b>"]
        L += [f"• {ofertas.linha(o, fontes.url_google)}" for o in sorted(of, key=lambda o: o["preco"])[:8]]
    L += ["", "<i>Toque no preço pra abrir no Google Voos. Te aviso na hora se algum cair bem abaixo do normal.</i>"]
    return "\n".join(L)
