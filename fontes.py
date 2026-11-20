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


def calendario(origem: str, destino: str, inicio: str, fim: str, adultos: int, noites: int | None, token: str) -> dict[str, dict]:
    """Menor preço de cada dia entre inicio e fim. Retorna {AAAA-MM-DD: {preco, url}}."""
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


def detalhes_voo(origem: str, destino: str, data: str, adultos: int, chave: str) -> dict | None:
    """Voo mais barato do dia, com horários (SerpAPI google_flights). Gasta 1 busca."""
    if not chave:
        return None
    p = {"engine": "google_flights", "departure_id": origem, "arrival_id": destino, "outbound_date": data,
         "type": 2, "adults": adultos, "currency": "BRL", "hl": "pt", "gl": "br", "sort_by": 2, "api_key": chave}
    try:
        d = requests.get("https://serpapi.com/search.json", params=p, timeout=60).json()
    except requests.RequestException:
        return None
    voos = (d.get("best_flights") or []) + (d.get("other_flights") or [])
    voos = [v for v in voos if isinstance(v.get("price"), (int, float)) and v.get("flights")]
    if not voos:
        return None
    v = min(voos, key=lambda x: x["price"])
    ini, fim = v["flights"][0], v["flights"][-1]
    return {
        "preco": v["price"], "cia": ", ".join(sorted({f.get("airline", "?") for f in v["flights"]})),
        "saida": ini["departure_airport"]["time"], "chegada": fim["arrival_airport"]["time"],
        "paradas": len(v["flights"]) - 1, "url": d.get("search_metadata", {}).get("google_flights_url") or url_google(origem, destino, data),
    }
