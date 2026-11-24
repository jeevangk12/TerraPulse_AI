from typing import TypedDict


class Location(TypedDict):
    latitude: float
    longitude: float


# City-centre demo points. Mandya's point is the example supplied in spec.md.
LOCATIONS: dict[str, Location] = {
    "Bengaluru": {"latitude": 12.9716, "longitude": 77.5946},
    "Mandya": {"latitude": 12.5218, "longitude": 76.8951},
    "Mysuru": {"latitude": 12.2958, "longitude": 76.6394},
    "Belagavi": {"latitude": 15.8497, "longitude": 74.4977},
    "Hubballi": {"latitude": 15.3647, "longitude": 75.1240},
    "Raichur": {"latitude": 16.2076, "longitude": 77.3463},
    "Kalaburagi": {"latitude": 17.3297, "longitude": 76.8343},
}


def find_location(name: str) -> tuple[str, Location] | None:
    normalized = name.strip().casefold()
    for canonical, coordinates in LOCATIONS.items():
        if canonical.casefold() == normalized:
            return canonical, coordinates
    return None
