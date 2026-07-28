"""Curated world airport directory for name / city search and route maps."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from pydantic import BaseModel


class AirportRecord(TypedDict):
    iata: str
    name: str
    city: str
    country: str
    lat: float
    lon: float


class AirportSearchResult(BaseModel):
    iata: str
    name: str
    city: str
    country: str
    label: str
    lat: Optional[float] = None
    lon: Optional[float] = None


# Representative global airports (IATA, name, city, country, lat, lon)
_AIRPORTS: List[AirportRecord] = [
    {"iata": "JFK", "name": "John F. Kennedy International", "city": "New York", "country": "USA", "lat": 40.6413, "lon": -73.7781},
    {"iata": "LGA", "name": "LaGuardia", "city": "New York", "country": "USA", "lat": 40.7769, "lon": -73.8740},
    {"iata": "EWR", "name": "Newark Liberty International", "city": "Newark", "country": "USA", "lat": 40.6895, "lon": -74.1745},
    {"iata": "LAX", "name": "Los Angeles International", "city": "Los Angeles", "country": "USA", "lat": 33.9425, "lon": -118.4081},
    {"iata": "SFO", "name": "San Francisco International", "city": "San Francisco", "country": "USA", "lat": 37.6213, "lon": -122.3790},
    {"iata": "ORD", "name": "O'Hare International", "city": "Chicago", "country": "USA", "lat": 41.9742, "lon": -87.9073},
    {"iata": "MDW", "name": "Midway International", "city": "Chicago", "country": "USA", "lat": 41.7868, "lon": -87.7522},
    {"iata": "MIA", "name": "Miami International", "city": "Miami", "country": "USA", "lat": 25.7959, "lon": -80.2870},
    {"iata": "BOS", "name": "Logan International", "city": "Boston", "country": "USA", "lat": 42.3656, "lon": -71.0096},
    {"iata": "SEA", "name": "Seattle-Tacoma International", "city": "Seattle", "country": "USA", "lat": 47.4502, "lon": -122.3088},
    {"iata": "ATL", "name": "Hartsfield-Jackson Atlanta International", "city": "Atlanta", "country": "USA", "lat": 33.6407, "lon": -84.4277},
    {"iata": "DFW", "name": "Dallas/Fort Worth International", "city": "Dallas", "country": "USA", "lat": 32.8998, "lon": -97.0403},
    {"iata": "DEN", "name": "Denver International", "city": "Denver", "country": "USA", "lat": 39.8561, "lon": -104.6737},
    {"iata": "LAS", "name": "Harry Reid International", "city": "Las Vegas", "country": "USA", "lat": 36.0840, "lon": -115.1537},
    {"iata": "PHX", "name": "Phoenix Sky Harbor International", "city": "Phoenix", "country": "USA", "lat": 33.4373, "lon": -112.0078},
    {"iata": "IAH", "name": "George Bush Intercontinental", "city": "Houston", "country": "USA", "lat": 29.9902, "lon": -95.3368},
    {"iata": "CLT", "name": "Charlotte Douglas International", "city": "Charlotte", "country": "USA", "lat": 35.2140, "lon": -80.9431},
    {"iata": "MSP", "name": "Minneapolis–Saint Paul International", "city": "Minneapolis", "country": "USA", "lat": 44.8848, "lon": -93.2223},
    {"iata": "DTW", "name": "Detroit Metropolitan Wayne County", "city": "Detroit", "country": "USA", "lat": 42.2162, "lon": -83.3554},
    {"iata": "LHR", "name": "Heathrow", "city": "London", "country": "UK", "lat": 51.4700, "lon": -0.4543},
    {"iata": "LGW", "name": "Gatwick", "city": "London", "country": "UK", "lat": 51.1537, "lon": -0.1821},
    {"iata": "STN", "name": "Stansted", "city": "London", "country": "UK", "lat": 51.8860, "lon": 0.2389},
    {"iata": "CDG", "name": "Charles de Gaulle", "city": "Paris", "country": "France", "lat": 49.0097, "lon": 2.5479},
    {"iata": "ORY", "name": "Orly", "city": "Paris", "country": "France", "lat": 48.7233, "lon": 2.3794},
    {"iata": "AMS", "name": "Amsterdam Schiphol", "city": "Amsterdam", "country": "Netherlands", "lat": 52.3105, "lon": 4.7683},
    {"iata": "FRA", "name": "Frankfurt am Main", "city": "Frankfurt", "country": "Germany", "lat": 50.0379, "lon": 8.5622},
    {"iata": "MUC", "name": "Munich", "city": "Munich", "country": "Germany", "lat": 48.3538, "lon": 11.7861},
    {"iata": "FCO", "name": "Leonardo da Vinci–Fiumicino", "city": "Rome", "country": "Italy", "lat": 41.8003, "lon": 12.2389},
    {"iata": "MXP", "name": "Malpensa", "city": "Milan", "country": "Italy", "lat": 45.6306, "lon": 8.7281},
    {"iata": "MAD", "name": "Adolfo Suárez Madrid–Barajas", "city": "Madrid", "country": "Spain", "lat": 40.4983, "lon": -3.5676},
    {"iata": "BCN", "name": "Barcelona–El Prat", "city": "Barcelona", "country": "Spain", "lat": 41.2974, "lon": 2.0833},
    {"iata": "LIS", "name": "Humberto Delgado", "city": "Lisbon", "country": "Portugal", "lat": 38.7742, "lon": -9.1342},
    {"iata": "DUB", "name": "Dublin", "city": "Dublin", "country": "Ireland", "lat": 53.4264, "lon": -6.2499},
    {"iata": "ZRH", "name": "Zurich", "city": "Zurich", "country": "Switzerland", "lat": 47.4582, "lon": 8.5555},
    {"iata": "VIE", "name": "Vienna International", "city": "Vienna", "country": "Austria", "lat": 48.1103, "lon": 16.5697},
    {"iata": "CPH", "name": "Copenhagen", "city": "Copenhagen", "country": "Denmark", "lat": 55.6180, "lon": 12.6560},
    {"iata": "ARN", "name": "Stockholm Arlanda", "city": "Stockholm", "country": "Sweden", "lat": 59.6519, "lon": 17.9186},
    {"iata": "OSL", "name": "Oslo Gardermoen", "city": "Oslo", "country": "Norway", "lat": 60.1939, "lon": 11.1004},
    {"iata": "HEL", "name": "Helsinki-Vantaa", "city": "Helsinki", "country": "Finland", "lat": 60.3172, "lon": 24.9633},
    {"iata": "IST", "name": "Istanbul", "city": "Istanbul", "country": "Turkey", "lat": 41.2753, "lon": 28.7519},
    {"iata": "DXB", "name": "Dubai International", "city": "Dubai", "country": "UAE", "lat": 25.2532, "lon": 55.3657},
    {"iata": "DOH", "name": "Hamad International", "city": "Doha", "country": "Qatar", "lat": 25.2731, "lon": 51.6080},
    {"iata": "AUH", "name": "Zayed International", "city": "Abu Dhabi", "country": "UAE", "lat": 24.4330, "lon": 54.6511},
    {"iata": "DEL", "name": "Indira Gandhi International", "city": "Delhi", "country": "India", "lat": 28.5562, "lon": 77.1000},
    {"iata": "BOM", "name": "Chhatrapati Shivaji Maharaj International", "city": "Mumbai", "country": "India", "lat": 19.0896, "lon": 72.8656},
    {"iata": "BLR", "name": "Kempegowda International", "city": "Bangalore", "country": "India", "lat": 13.1986, "lon": 77.7066},
    {"iata": "SIN", "name": "Changi", "city": "Singapore", "country": "Singapore", "lat": 1.3644, "lon": 103.9915},
    {"iata": "HKG", "name": "Hong Kong International", "city": "Hong Kong", "country": "China", "lat": 22.3080, "lon": 113.9185},
    {"iata": "PVG", "name": "Shanghai Pudong International", "city": "Shanghai", "country": "China", "lat": 31.1443, "lon": 121.8083},
    {"iata": "PEK", "name": "Beijing Capital International", "city": "Beijing", "country": "China", "lat": 40.0799, "lon": 116.6031},
    {"iata": "NRT", "name": "Narita International", "city": "Tokyo", "country": "Japan", "lat": 35.7720, "lon": 140.3929},
    {"iata": "HND", "name": "Haneda", "city": "Tokyo", "country": "Japan", "lat": 35.5494, "lon": 139.7798},
    {"iata": "KIX", "name": "Kansai International", "city": "Osaka", "country": "Japan", "lat": 34.4347, "lon": 135.2440},
    {"iata": "ICN", "name": "Incheon International", "city": "Seoul", "country": "South Korea", "lat": 37.4602, "lon": 126.4407},
    {"iata": "BKK", "name": "Suvarnabhumi", "city": "Bangkok", "country": "Thailand", "lat": 13.6900, "lon": 100.7501},
    {"iata": "KUL", "name": "Kuala Lumpur International", "city": "Kuala Lumpur", "country": "Malaysia", "lat": 2.7456, "lon": 101.7072},
    {"iata": "SYD", "name": "Kingsford Smith", "city": "Sydney", "country": "Australia", "lat": -33.9399, "lon": 151.1753},
    {"iata": "MEL", "name": "Melbourne", "city": "Melbourne", "country": "Australia", "lat": -37.6690, "lon": 144.8410},
    {"iata": "AKL", "name": "Auckland", "city": "Auckland", "country": "New Zealand", "lat": -37.0082, "lon": 174.7850},
    {"iata": "YYZ", "name": "Toronto Pearson International", "city": "Toronto", "country": "Canada", "lat": 43.6777, "lon": -79.6248},
    {"iata": "YVR", "name": "Vancouver International", "city": "Vancouver", "country": "Canada", "lat": 49.1967, "lon": -123.1815},
    {"iata": "YUL", "name": "Montréal–Trudeau International", "city": "Montreal", "country": "Canada", "lat": 45.4706, "lon": -73.7408},
    {"iata": "MEX", "name": "Benito Juárez International", "city": "Mexico City", "country": "Mexico", "lat": 19.4363, "lon": -99.0721},
    {"iata": "CUN", "name": "Cancún International", "city": "Cancún", "country": "Mexico", "lat": 21.0365, "lon": -86.8771},
    {"iata": "GRU", "name": "São Paulo/Guarulhos", "city": "São Paulo", "country": "Brazil", "lat": -23.4356, "lon": -46.4731},
    {"iata": "GIG", "name": "Rio de Janeiro/Galeão", "city": "Rio de Janeiro", "country": "Brazil", "lat": -22.8090, "lon": -43.2506},
    {"iata": "EZE", "name": "Ministro Pistarini International", "city": "Buenos Aires", "country": "Argentina", "lat": -34.8222, "lon": -58.5358},
    {"iata": "SCL", "name": "Arturo Merino Benítez International", "city": "Santiago", "country": "Chile", "lat": -33.3930, "lon": -70.7858},
    {"iata": "BOG", "name": "El Dorado International", "city": "Bogotá", "country": "Colombia", "lat": 4.7016, "lon": -74.1469},
    {"iata": "LIM", "name": "Jorge Chávez International", "city": "Lima", "country": "Peru", "lat": -12.0219, "lon": -77.1143},
    {"iata": "JNB", "name": "O. R. Tambo International", "city": "Johannesburg", "country": "South Africa", "lat": -26.1367, "lon": 28.2411},
    {"iata": "CPT", "name": "Cape Town International", "city": "Cape Town", "country": "South Africa", "lat": -33.9649, "lon": 18.6017},
    {"iata": "CAI", "name": "Cairo International", "city": "Cairo", "country": "Egypt", "lat": 30.1219, "lon": 31.4056},
    {"iata": "NBO", "name": "Jomo Kenyatta International", "city": "Nairobi", "country": "Kenya", "lat": -1.3192, "lon": 36.9278},
    {"iata": "ADD", "name": "Bole International", "city": "Addis Ababa", "country": "Ethiopia", "lat": 8.9779, "lon": 38.7993},
    {"iata": "RUH", "name": "King Khalid International", "city": "Riyadh", "country": "Saudi Arabia", "lat": 24.9578, "lon": 46.6989},
    {"iata": "TLV", "name": "Ben Gurion", "city": "Tel Aviv", "country": "Israel", "lat": 32.0114, "lon": 34.8867},
]

_BY_IATA: Dict[str, AirportRecord] = {a["iata"]: a for a in _AIRPORTS}

CARRIER_NAMES: Dict[str, str] = {
    "AA": "American Airlines",
    "UA": "United Airlines",
    "DL": "Delta Air Lines",
    "B6": "JetBlue Airways",
    "AS": "Alaska Airlines",
    "WN": "Southwest Airlines",
    "BA": "British Airways",
    "AF": "Air France",
    "LH": "Lufthansa",
    "KL": "KLM",
    "EK": "Emirates",
    "QR": "Qatar Airways",
    "SQ": "Singapore Airlines",
    "NH": "All Nippon Airways",
    "JL": "Japan Airlines",
    "AC": "Air Canada",
    "IB": "Iberia",
    "LX": "Swiss International Air Lines",
    "TK": "Turkish Airlines",
    "EY": "Etihad Airways",
}

# Carrier-preferred hub airports for realistic connecting itineraries
_CARRIER_HUBS: Dict[str, List[str]] = {
    "AA": ["DFW", "CLT", "ORD", "MIA", "PHX"],
    "UA": ["ORD", "DEN", "IAH", "EWR", "SFO"],
    "DL": ["ATL", "MSP", "DTW", "JFK", "SEA"],
    "B6": ["JFK", "BOS", "FLL", "MCO"],
    "AS": ["SEA", "PDX", "SFO", "LAX"],
    "WN": ["DEN", "MDW", "LAS", "PHX", "BWI"],
    "BA": ["LHR", "LGW"],
    "AF": ["CDG", "ORY"],
    "LH": ["FRA", "MUC"],
    "KL": ["AMS"],
    "EK": ["DXB"],
    "QR": ["DOH"],
    "SQ": ["SIN"],
    "AC": ["YYZ", "YUL", "YVR"],
    "IB": ["MAD"],
    "LX": ["ZRH"],
    "TK": ["IST"],
    "EY": ["AUH"],
}

_MAJOR_HUBS = ["ATL", "ORD", "DFW", "DEN", "CLT", "AMS", "FRA", "LHR", "CDG", "DXB", "DOH", "IST", "SIN", "YYZ"]


def get_airport(iata: str) -> Optional[AirportRecord]:
    return _BY_IATA.get((iata or "").upper().strip())


def airport_name(iata: str) -> str:
    ap = get_airport(iata)
    return ap["name"] if ap else (iata or "").upper()


def airport_city(iata: str) -> str:
    ap = get_airport(iata)
    return ap["city"] if ap else (iata or "").upper()


def carrier_display_name(code: str) -> str:
    c = (code or "").upper().strip()
    return CARRIER_NAMES.get(c, c or "Unknown airline")


def airport_coords(iata: str) -> Optional[tuple[float, float]]:
    ap = get_airport(iata)
    if not ap:
        return None
    return ap["lat"], ap["lon"]


def _haversine_km(a: AirportRecord, b: AirportRecord) -> float:
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def estimate_block_minutes(origin: str, destination: str) -> int:
    """Rough block time from great-circle distance (includes taxi/climb buffer)."""
    a, b = get_airport(origin), get_airport(destination)
    if not a or not b:
        return 150
    km = _haversine_km(a, b)
    # ~780 km/h cruise + 40 min ground buffer
    return max(55, int(km / 13.0) + 40)


def pick_layover_hubs(origin: str, destination: str, stops: int, carrier: str, seed: int) -> List[str]:
    """Pick realistic intermediate hubs that are not origin/destination."""
    origin_u = origin.upper()
    dest_u = destination.upper()
    banned = {origin_u, dest_u}
    preferred = [h for h in _CARRIER_HUBS.get(carrier.upper(), []) if h not in banned and get_airport(h)]
    fallback = [h for h in _MAJOR_HUBS if h not in banned and get_airport(h)]

    # Route-aware preferences for common city pairs
    pair_prefs: Dict[tuple[str, str], List[str]] = {
        ("JFK", "LAX"): ["ORD", "DFW", "DEN", "ATL"],
        ("LAX", "JFK"): ["ORD", "DFW", "DEN", "ATL"],
        ("JFK", "SFO"): ["ORD", "DEN", "DFW"],
        ("SFO", "JFK"): ["ORD", "DEN", "DFW"],
        ("JFK", "LHR"): ["BOS", "DUB", "YYZ"],
        ("LHR", "JFK"): ["DUB", "AMS", "YYZ"],
        ("LAX", "NRT"): ["SFO", "SEA", "ICN"],
        ("NRT", "LAX"): ["HND", "ICN", "SEA"],
        ("JFK", "CDG"): ["BOS", "DUB", "AMS"],
        ("CDG", "JFK"): ["AMS", "LHR", "DUB"],
        ("SFO", "LHR"): ["SEA", "ORD", "YYZ"],
        ("LHR", "SFO"): ["ORD", "YYZ", "DUB"],
    }
    route_hubs = [h for h in pair_prefs.get((origin_u, dest_u), []) if h not in banned and get_airport(h)]

    o = get_airport(origin_u)
    d = get_airport(dest_u)
    both_us = bool(o and d and o["country"] == "USA" and d["country"] == "USA")
    us_only = {"ATL", "ORD", "DFW", "DEN", "CLT", "MSP", "DTW", "IAH", "PHX", "LAS", "SEA", "SFO", "LAX", "JFK", "EWR", "BOS", "MIA", "MDW"}

    pool = route_hubs + preferred + fallback
    if both_us:
        pool = [h for h in pool if h in us_only] or [h for h in ["ORD", "DFW", "DEN", "ATL", "CLT"] if h not in banned]

    # de-dupe preserving order
    seen = set()
    ordered: List[str] = []
    for h in pool:
        if h not in seen:
            seen.add(h)
            ordered.append(h)
    if not ordered:
        ordered = ["ATL", "ORD", "DFW"]

    hubs: List[str] = []
    idx = seed % len(ordered)
    for i in range(max(0, stops)):
        hubs.append(ordered[(idx + i) % len(ordered)])
        # avoid repeating same hub consecutively when possible
        if len(ordered) > 1 and i + 1 < stops and hubs[-1] == ordered[(idx + i + 1) % len(ordered)]:
            idx += 1
    # ensure uniqueness for multi-stop when possible
    if stops >= 2 and len(set(hubs)) < 2 and len(ordered) >= 2:
        hubs = [ordered[idx % len(ordered)], ordered[(idx + 1) % len(ordered)]][:stops]
    return hubs[:stops]


def search_airports(query: str, limit: int = 12) -> List[AirportSearchResult]:
    q = (query or "").strip().lower()
    if len(q) < 1:
        return []
    scored: List[tuple[int, AirportRecord]] = []
    for ap in _AIRPORTS:
        hay = f"{ap['iata']} {ap['name']} {ap['city']} {ap['country']}".lower()
        if q not in hay and not (len(q) == 3 and ap["iata"].lower() == q):
            parts = hay.replace("–", " ").replace("-", " ").split()
            if not any(p.startswith(q) for p in parts):
                continue
        score = 0
        if ap["iata"].lower() == q:
            score += 100
        if q in ap["city"].lower():
            score += 50
        if q in ap["name"].lower():
            score += 40
        if ap["iata"].lower().startswith(q):
            score += 30
        scored.append((score, ap))
    scored.sort(key=lambda x: (-x[0], x[1]["iata"]))
    out: List[AirportSearchResult] = []
    for _, ap in scored[:limit]:
        out.append(
            AirportSearchResult(
                iata=ap["iata"],
                name=ap["name"],
                city=ap["city"],
                country=ap["country"],
                label=f"{ap['city']} — {ap['name']} ({ap['iata']})",
                lat=ap["lat"],
                lon=ap["lon"],
            )
        )
    return out
