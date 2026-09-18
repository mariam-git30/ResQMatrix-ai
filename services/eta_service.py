"""Estimated travel time helpers.

ETAs in this module are estimates from straight-line distance and configured
speeds. They are not live traffic routing.
"""

from __future__ import annotations

from typing import Any, Mapping


DEFAULT_SPEEDS_KMH: dict[str, float] = {
    "AMBULANCE": 40.0,
    "FIRE_ENGINE": 35.0,
    "RESCUE_TEAM": 30.0,
    "RESCUE_BOAT": 15.0,
    "MEDICAL_TEAM": 30.0,
    "HELICOPTER": 120.0,
}
DEFAULT_SPEED_KMH = 30.0


def estimated_eta_minutes(
    distance_km: float | None,
    resource_type: Any,
    speeds_kmh: Mapping[str, float] | None = None,
    *,
    default_speed_kmh: float = DEFAULT_SPEED_KMH,
) -> float | None:
    """Convert distance to estimated minutes using a configurable speed."""
    if distance_km is None:
        return None
    try:
        distance = float(distance_km)
    except (TypeError, ValueError):
        return None
    if distance < 0:
        return None
    speeds = dict(DEFAULT_SPEEDS_KMH)
    if speeds_kmh:
        speeds.update(
            {str(key).upper(): float(value) for key, value in speeds_kmh.items()}
        )
    speed = speeds.get(str(resource_type or "").upper(), default_speed_kmh)
    if speed <= 0:
        return None
    return round((distance / speed) * 60, 2)


def estimate_eta(
    emergency: Mapping[str, Any],
    resource: Mapping[str, Any],
    speeds_kmh: Mapping[str, float] | None = None,
) -> float | None:
    """Estimate ETA from emergency/resource coordinates."""
    from .distance_service import haversine_distance

    distance = haversine_distance(
        emergency.get("latitude"),
        emergency.get("longitude"),
        resource.get("latitude"),
        resource.get("longitude"),
    )
    return estimated_eta_minutes(
        distance,
        resource.get("type"),
        speeds_kmh,
    )
