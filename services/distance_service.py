"""Local geographic distance helpers."""

from __future__ import annotations

import math
from typing import Any


EARTH_RADIUS_KM = 6371.0


def haversine_distance(
    latitude_one: Any,
    longitude_one: Any,
    latitude_two: Any,
    longitude_two: Any,
) -> float | None:
    """Return great-circle distance in kilometres, or None for bad coordinates."""
    try:
        lat_one = float(latitude_one)
        lon_one = float(longitude_one)
        lat_two = float(latitude_two)
        lon_two = float(longitude_two)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (lat_one, lon_one, lat_two, lon_two)):
        return None
    if not (-90 <= lat_one <= 90 and -90 <= lat_two <= 90):
        return None
    if not (-180 <= lon_one <= 180 and -180 <= lon_two <= 180):
        return None

    lat_one_rad, lat_two_rad = math.radians(lat_one), math.radians(lat_two)
    delta_lat = math.radians(lat_two - lat_one)
    delta_lon = math.radians(lon_two - lon_one)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_one_rad)
        * math.cos(lat_two_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    return round(
        EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(min(1.0, haversine))),
        2,
    )


# A concise alias for callers that prefer service-oriented naming.
distance_km = haversine_distance
