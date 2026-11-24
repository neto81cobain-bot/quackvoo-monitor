import logging, sys, traceback
logging.basicConfig(level=logging.DEBUG)
from datetime import date, timedelta
from fli.core.builders import build_date_search_segments
from fli.models import Airport, DateSearchFilters, PassengerInfo, SeatType, MaxStops
from fli.search import SearchDates
for (o,d,a,b) in [("JFK","LHR","2027-01-10","2027-01-20"),("MAO","VVI","2027-05-25","2027-06-20"),("MAO","GRU","2027-01-10","2027-01-20")]:
    segs, tipo = build_date_search_segments(origin=getattr(Airport,o), destination=getattr(Airport,d), start_date=a)
    f = DateSearchFilters(trip_type=tipo, passenger_info=PassengerInfo(adults=1), flight_segments=segs, stops=MaxStops.ANY, seat_type=SeatType.ECONOMY, from_date=a, to_date=b)
    s = SearchDates()
    try:
        r = s.search(f, currency="BRL", language="pt-BR", country="BR")
        print(o,d,"->", None if r is None else len(r), r[:2] if r else "")
        r2 = s.search(f)
        print(o,d,"sem locale ->", None if r2 is None else len(r2), r2[:2] if r2 else "")
    except Exception: traceback.print_exc()
