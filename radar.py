"""Radar do Norte 🌴 — pra onde está barato voar saindo de Manaus, Belém, Santarém e Trombetas.

Usa a busca "Explorar" do Google Voos (pela biblioteca grátis Fli), guarda o preço de cada destino ao
longo dos dias e avisa quando um cair bem abaixo do normal. Domingo manda o resumo da semana.
"""
from datetime import date, timedelta
from statistics import median

import analise as A
import fontes
import inteligencia as I
from aeroportos import nome as nome_aero

ORIGENS_PADRAO = ["MAO", "BEL", "STM", "TMT"]
OFFSETS = [10, 17, 24, 31, 38, 45, 52, 59, 66, 73, 80, 87]  # dias à frente, revezados a cada rodada


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


def rodar(est: dict, origens: list[str], agora_iso: str, rodada: int) -> list[dict]:
    """Uma varredura. Atualiza o histórico em `est` e devolve as ofertas que merecem aviso agora."""
    rad = est.setdefault("radar", {"hist": {}, "alertas": {}})
    hoje = date.today()
    offs = [OFFSETS[(rodada + k * 4) % len(OFFSETS)] for k in range(3)]
    boas = []
    for o in origens:
        for off in offs:
            data = (hoje + timedelta(days=off)).isoformat()
            for x in explorar(o, data):
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
    url = fontes.url_google(x["origem"], x["dest"], x["data"])
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
    L.append("<i>Preço só de ida, com taxas. Promoção assim costuma durar pouco.</i>")
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
    if not ult:
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
    L += ["", "<i>Toque no preço pra abrir no Google Voos. Te aviso na hora se algum cair bem abaixo do normal.</i>"]
    return "\n".join(L)
