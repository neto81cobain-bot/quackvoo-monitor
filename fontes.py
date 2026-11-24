"""De onde vêm os preços: calendário do Google Voos (Apify) e detalhes do voo (SerpAPI)."""
import json, os, time
from datetime import date, timedelta
import requests

ATOR = "lergassy~flight-price-calendar"


class ErroFonte(Exception):
    pass


def dia(s: str) -> date:
    return date.fromisoformat(str(s))


def url_google(origem: str, destino: str, ida: str, volta: str | None = None) -> str:
    q = f"Flights from {origem} to {destino} on {ida}" + (f" returning {volta}" if volta else " one way")
    return "https://www.google.com/travel/flights?hl=pt-BR&curr=BRL&q=" + requests.utils.quote(q)


def calendario_fli(origem: str, destino: str, inicio: str, fim: str, adultos: int, noites: int | None) -> dict[str, dict]:
    """Mesmo calendário do Google Voos, de graça, pela biblioteca aberta Fli (API interna do Google).
    Não oficial: pode quebrar se o Google mudar algo. Retorna {AAAA-MM-DD: {preco, url}}."""
    try:
        from fli.core.builders import build_date_search_segments
        from fli.models import Airport, DateSearchFilters, PassengerInfo, SeatType, MaxStops
        from fli.search import SearchDates
    except ImportError as e:
        raise ErroFonte(f"Fli não instalado ({e}).")
    hoje = date.today() + timedelta(days=1)
    ini = max(dia(inicio), hoje)
    fim_d = min(dia(fim), date.today() + timedelta(days=300))
    if ini > fim_d:
        return {}
    try:
        o, d_ = getattr(Airport, origem), getattr(Airport, destino)
    except AttributeError as e:
        raise ErroFonte(f"Fli não conhece o aeroporto {e}.")
    # o Google não entrega mais a grade de calendário: cada data é uma página (~2 MB), até 93 por busca
    res, ultimo, a = [], None, ini
    while a <= fim_d:
        b = min(a + timedelta(days=89), fim_d)
        segs, tipo = build_date_search_segments(origin=o, destination=d_, start_date=a.isoformat(),
                                                trip_duration=noites or None, is_round_trip=bool(noites))
        filtros = DateSearchFilters(trip_type=tipo, passenger_info=PassengerInfo(adults=adultos), flight_segments=segs,
                                    stops=MaxStops.ANY, seat_type=SeatType.ECONOMY, from_date=a.isoformat(),
                                    to_date=b.isoformat(), duration=noites or None)
        for tentativa in range(2):
            try:
                res += SearchDates().search(filtros, currency="BRL", language="pt-BR", country="BR") or []
                break
            except Exception as e:  # rede, bloqueio, resposta mudou
                ultimo = e
                time.sleep(10)
        a = b + timedelta(days=1)
    if not res and ultimo:
        raise ErroFonte(f"Fli falhou: {str(ultimo)[:160]}")
    saida = {}
    for item in res:
        k = item.date[0].date().isoformat()
        if not (ini.isoformat() <= k <= fim_d.isoformat()) or not item.price:
            continue
        volta = (dia(k) + timedelta(days=noites)).isoformat() if noites else None
        if k not in saida or item.price < saida[k]["preco"]:
            saida[k] = {"preco": round(item.price), "url": url_google(origem, destino, k, volta)}
    return saida


def calendario(origem: str, destino: str, inicio: str, fim: str, adultos: int, noites: int | None, token: str,
               fonte: str = "auto") -> dict[str, dict]:
    """Escolhe a fonte: 'apify', 'fli' ou 'auto' (Apify e, se faltar crédito/token ou falhar, Fli)."""
    if fonte == "fli" or (fonte == "auto" and not token):
        return calendario_fli(origem, destino, inicio, fim, adultos, noites)
    if fonte == "fli_primeiro":  # pernas das escalas: grátis primeiro; Apify só se o Fli cobrir pouco
        try:
            r = calendario_fli(origem, destino, inicio, fim, adultos, noites)
        except ErroFonte as e:
            print(f"Fli {origem}→{destino}: {e}"); r = {}
        hoje = date.today() + timedelta(days=1)
        esperados = (dia(fim) - max(dia(inicio), hoje)).days + 1
        if esperados <= 0 or len(r) >= 0.8 * esperados or not token:
            FONTE_USADA.add("fli")
            return r
        print(f"Fli cobriu só {len(r)}/{esperados} dias de {origem}→{destino}; completando com a Apify")
    try:
        return calendario_apify(origem, destino, inicio, fim, adultos, noites, token)
    except ErroFonte as e:
        if fonte != "auto":
            raise
        print(f"Apify falhou ({e}); usando o Fli (grátis)")
        FONTE_USADA.add("fli")
        return calendario_fli(origem, destino, inicio, fim, adultos, noites)


FONTE_USADA: set = set()
DIAS_APIFY = 0  # dias de calendário cobrados pela Apify nesta execução


def calendario_apify(origem: str, destino: str, inicio: str, fim: str, adultos: int, noites: int | None, token: str) -> dict[str, dict]:
    """Menor preço de cada dia entre inicio e fim (Apify). Retorna {AAAA-MM-DD: {preco, url}}."""
    hoje = date.today() + timedelta(days=1)
    ini = max(dia(inicio), hoje)
    if ini > dia(fim):
        return {}
    dias = (dia(fim) - ini).days + 1
    entrada = {
        "origin": origem, "destination": destino, "departureDate": ini.isoformat(),
        "adults": adultos, "cabinClass": "economy", "currency": "BRL", "market": "BR", "language": "pt",
        "calendarDays": min(dias, 365), "calendarOnly": True, "includeSearchSummary": False,
        "includeRunSummary": False, "routes": [], "multiCityLegs": [],
    }
    if noites:
        entrada["returnDate"] = (ini + timedelta(days=noites)).isoformat()
    global DIAS_APIFY
    DIAS_APIFY += min(dias, 365)
    url = f"https://api.apify.com/v2/acts/{ATOR}/run-sync-get-dataset-items?token={token}&timeout=240"
    for tentativa in range(3):
        try:
            r = requests.post(url, json=entrada, timeout=260)
        except requests.RequestException as e:
            if tentativa == 2:
                raise ErroFonte(f"Apify fora do ar: {e}")
            time.sleep(10); continue
        if r.status_code in (401, 403):
            raise ErroFonte("Token da Apify recusado (confira o segredo APIFY_TOKEN).")
        if r.status_code == 402:
            raise ErroFonte("Acabaram os créditos grátis da Apify neste mês.")
        if r.ok:
            break
        if tentativa == 2:
            raise ErroFonte(f"Apify respondeu {r.status_code}: {r.text[:200]}")
        time.sleep(10)
    itens = r.json() if r.ok else []
    saida: dict[str, dict] = {}
    for i in itens if isinstance(itens, list) else []:
        d, p = str(i.get("date", "")), i.get("price")
        if len(d) != 10 or not isinstance(p, (int, float)) or (i.get("type") and "calendar" not in str(i.get("type"))):
            continue
        if d > fim:
            continue
        if d not in saida or p < saida[d]["preco"]:
            volta = (dia(d) + timedelta(days=noites)).isoformat() if noites else None
            saida[d] = {"preco": round(p), "url": i.get("googleFlightsUrl") or url_google(origem, destino, d, volta)}
    return saida


def detalhes_voo(origem: str, destino: str, data: str, adultos: int, chave: str, volta: str | None = None) -> dict | None:
    """Voo mais barato do dia, com horários e a opinião do Google sobre o preço (SerpAPI). Gasta 1 busca."""
    if not chave:
        return None
    p = {"engine": "google_flights", "departure_id": origem, "arrival_id": destino, "outbound_date": data,
         "type": 1 if volta else 2, "adults": adultos, "currency": "BRL", "hl": "pt", "gl": "br", "sort_by": 2, "api_key": chave}
    if volta:
        p["return_date"] = volta
    try:
        d = requests.get("https://serpapi.com/search.json", params=p, timeout=60).json()
    except (requests.RequestException, ValueError):
        return None
    pi = d.get("price_insights") or {}
    google = {}
    if isinstance(pi.get("typical_price_range"), list) and len(pi["typical_price_range"]) == 2:
        google["faixa"] = pi["typical_price_range"]
    if pi.get("price_level"):
        google["nivel"] = pi["price_level"]
    if pi.get("lowest_price"):
        google["menor"] = pi["lowest_price"]
    voos = (d.get("best_flights") or []) + (d.get("other_flights") or [])
    voos = [v for v in voos if isinstance(v.get("price"), (int, float)) and v.get("flights")]
    if not voos:
        return {"google": google} if google else None
    v = min(voos, key=lambda x: x["price"])
    ini, fim = v["flights"][0], v["flights"][-1]
    return {
        "preco": v["price"], "cia": ", ".join(sorted({f.get("airline", "?") for f in v["flights"]})),
        "saida": ini["departure_airport"]["time"], "chegada": fim["arrival_airport"]["time"],
        "paradas": len(v["flights"]) - 1, "google": google, "url": d.get("search_metadata", {}).get("google_flights_url") or url_google(origem, destino, data),
    }


# ---------------------------------------------------------------- créditos
def apify_uso(token: str) -> dict | None:
    """Quanto da cota grátis da Apify já foi usado neste mês: {usado, limite, pct}."""
    if not token:
        return None
    try:
        d = requests.get("https://api.apify.com/v2/users/me/limits", params={"token": token}, timeout=30).json().get("data", {})
        usado = float(d.get("current", {}).get("monthlyUsageUsd") or 0)
        limite = float(d.get("limits", {}).get("maxMonthlyUsageUsd") or 5)
        return {"usado": usado, "limite": limite, "pct": usado / limite if limite else 0}
    except Exception:
        return None


def serp_restante(chave: str) -> int | None:
    if not chave:
        return None
    try:
        d = requests.get("https://serpapi.com/account.json", params={"api_key": chave}, timeout=30).json()
        v = d.get("total_searches_left", d.get("plan_searches_left"))
        return int(v) if v is not None else None
    except Exception:
        return None
