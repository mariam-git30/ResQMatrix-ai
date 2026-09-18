"""Transparent emergency/resource compatibility rules for Step 4A."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


COMPATIBILITY_MATRIX: dict[str, tuple[str, ...]] = {
    "FIRE": ("FIRE_ENGINE", "RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM"),
    "FLOOD": (
        "RESCUE_BOAT",
        "RESCUE_TEAM",
        "AMBULANCE",
        "MEDICAL_TEAM",
        "MEDICAL_KIT",
    ),
    "ROAD_ACCIDENT": (
        "AMBULANCE",
        "MEDICAL_TEAM",
        "RESCUE_TEAM",
        "MEDICAL_KIT",
    ),
    "BUILDING_COLLAPSE": (
        "RESCUE_TEAM",
        "AMBULANCE",
        "MEDICAL_TEAM",
        "HELICOPTER",
        "MEDICAL_KIT",
    ),
    "MEDICAL": ("AMBULANCE", "MEDICAL_TEAM", "MEDICAL_KIT", "BLOOD_UNIT"),
    "LANDSLIDE": ("RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM", "HELICOPTER"),
    "CYCLONE": (
        "RESCUE_TEAM",
        "RESCUE_BOAT",
        "AMBULANCE",
        "MEDICAL_TEAM",
        "HELICOPTER",
        "WATER_SUPPLY",
        "FOOD_SUPPLY",
        "SHELTER_KIT",
    ),
    "CHEMICAL": ("RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM", "MEDICAL_KIT"),
    "OTHER": ("RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM"),
}

UNAVAILABLE_STATUSES = {"MAINTENANCE", "UNAVAILABLE"}
AVAILABLE_STATUSES = {"AVAILABLE", "PARTIALLY_AVAILABLE", "DEPLOYED"}


def _value(record: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return record[key]
    except (KeyError, IndexError, TypeError):
        return default


def compatible_types(emergency_type: Any) -> tuple[str, ...]:
    """Return compatible resource types for an emergency type."""
    return COMPATIBILITY_MATRIX.get(str(emergency_type or "").upper(), ())


def is_compatible(emergency: Mapping[str, Any], resource: Mapping[str, Any]) -> bool:
    """Return true only for a resource type in the configured matrix."""
    return str(_value(resource, "type", "")).upper() in compatible_types(
        _value(emergency, "type")
    )


def is_available(resource: Mapping[str, Any]) -> bool:
    """Only resources with usable quantity and dispatchable status qualify."""
    status = str(_value(resource, "status", "")).upper()
    try:
        available_quantity = float(_value(resource, "available_quantity", 0))
    except (TypeError, ValueError):
        available_quantity = 0
    return (
        status not in UNAVAILABLE_STATUSES
        and status in AVAILABLE_STATUSES
        and available_quantity > 0
    )


def matching_resources(
    emergency: Mapping[str, Any],
    resources: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Filter out incompatible, unavailable, and zero-quantity resources."""
    return [
        resource
        for resource in resources
        if is_compatible(emergency, resource) and is_available(resource)
    ]
