import importlib.metadata as md
print("versão flights:", md.version("flights"))
from fli.core.builders import build_date_search_segments
from fli.models import Airport, DateSearchFilters, PassengerInfo, SeatType, MaxStops
from fli.search import SearchDates, SearchFlights
from fli.search._urls import with_locale_params
from fli.models import FlightSearchFilters
segs, tipo = build_date_search_segments(origin=Airport.JFK, destination=Airport.LHR, start_date="2027-01-10")
f = DateSearchFilters(trip_type=tipo, passenger_info=PassengerInfo(adults=1), flight_segments=segs, stops=MaxStops.ANY, seat_type=SeatType.ECONOMY, from_date="2027-01-10", to_date="2027-01-20")
s = SearchDates()
r = s.client.post(url=with_locale_params(s.BASE_URL, None, None, None), data=f"f.req={f.encode()}", impersonate="chrome", allow_redirects=True)
print("status", r.status_code, "url final", r.url)
print(r.text[:600].replace("\n"," | "))
try:
    from fli.models import FlightSegment
    ff = FlightSearchFilters(passenger_info=PassengerInfo(adults=1), flight_segments=segs, stops=MaxStops.ANY, seat_type=SeatType.ECONOMY)
    res = SearchFlights().search(ff)
    print("SearchFlights:", None if res is None else len(res))
except Exception as e: print("SearchFlights erro:", e)
