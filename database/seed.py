"""Clearly fictional simulation/demo data for ResQMatrix AI."""

from __future__ import annotations

import sqlite3
from typing import Any


DEMO_TAG = "[FICTIONAL DEMO]"

DEMO_EMERGENCIES = [
    {
        "title": "Monsoon flooding near East River Ward",
        "type": "FLOOD",
        "description": f"{DEMO_TAG} Rising water has isolated several residential blocks after sustained rainfall.",
        "location": "East River Ward",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "severity": 78,
        "people_affected": 320,
        "injured": 14,
        "critical_injured": 2,
        "urgency": 88,
        "reported_time": "2026-09-18T04:12:00+05:30",
        "status": "ACTIVE",
    },
    {
        "title": "Industrial fire at Northpoint Depot",
        "type": "FIRE",
        "description": f"{DEMO_TAG} A contained fire is producing heavy smoke near a logistics depot.",
        "location": "Northpoint Industrial Zone",
        "latitude": 19.076,
        "longitude": 72.8777,
        "severity": 91,
        "people_affected": 86,
        "injured": 21,
        "critical_injured": 5,
        "urgency": 94,
        "reported_time": "2026-09-18T03:46:00+05:30",
        "status": "IN_PROGRESS",
    },
    {
        "title": "Multi-vehicle collision on Ring Road",
        "type": "ROAD_ACCIDENT",
        "description": f"{DEMO_TAG} Traffic collision blocking two lanes and requiring coordinated medical response.",
        "location": "Ring Road, Sector 7",
        "latitude": 28.6139,
        "longitude": 77.209,
        "severity": 66,
        "people_affected": 31,
        "injured": 11,
        "critical_injured": 1,
        "urgency": 72,
        "reported_time": "2026-09-17T22:18:00+05:30",
        "status": "ACTIVE",
    },
    {
        "title": "Community shelter inspection",
        "type": "MEDICAL",
        "description": f"{DEMO_TAG} Temporary shelter requires a routine medical support review.",
        "location": "Central Community Hall",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "severity": 22,
        "people_affected": 74,
        "injured": 3,
        "critical_injured": 0,
        "urgency": 28,
        "reported_time": "2026-09-17T18:30:00+05:30",
        "status": "RESOLVED",
    },
    {
        "title": "Bridge collapse at Old Mill Crossing",
        "type": "BUILDING_COLLAPSE",
        "description": f"{DEMO_TAG} A damaged pedestrian bridge has collapsed near a crowded market approach.",
        "location": "Old Mill Crossing",
        "latitude": 17.385,
        "longitude": 78.4867,
        "severity": 87,
        "people_affected": 140,
        "injured": 38,
        "critical_injured": 9,
        "urgency": 97,
        "reported_time": "2026-09-18T02:28:00+05:30",
        "status": "ACTIVE",
    },
    {
        "title": "Hillside slide above Pine Hamlet",
        "type": "LANDSLIDE",
        "description": f"{DEMO_TAG} Saturated hillside soil has blocked the access road to several homes.",
        "location": "Pine Hamlet, Western Ridge",
        "latitude": 30.0668,
        "longitude": 79.0193,
        "severity": 73,
        "people_affected": 95,
        "injured": 8,
        "critical_injured": 1,
        "urgency": 81,
        "reported_time": "2026-09-17T21:05:00+05:30",
        "status": "IN_PROGRESS",
    },
    {
        "title": "Cyclone evacuation at Coastline Block",
        "type": "CYCLONE",
        "description": f"{DEMO_TAG} High winds and storm surge warnings are driving a coastal evacuation.",
        "location": "Coastline Block 3",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "severity": 84,
        "people_affected": 680,
        "injured": 17,
        "critical_injured": 3,
        "urgency": 92,
        "reported_time": "2026-09-18T01:16:00+05:30",
        "status": "ACTIVE",
    },
    {
        "title": "Chemical leak at Meridian Works",
        "type": "CHEMICAL",
        "description": f"{DEMO_TAG} A solvent leak has triggered a controlled perimeter and precautionary sheltering.",
        "location": "Meridian Works, Gate 2",
        "latitude": 23.0225,
        "longitude": 72.5714,
        "severity": 96,
        "people_affected": 210,
        "injured": 29,
        "critical_injured": 7,
        "urgency": 99,
        "reported_time": "2026-09-18T03:02:00+05:30",
        "status": "IN_PROGRESS",
    },
    {
        "title": "Cancelled evacuation drill at Harbor Terminal",
        "type": "OTHER",
        "description": f"{DEMO_TAG} A planned tabletop evacuation drill was cancelled before deployment.",
        "location": "Harbor Terminal Training Zone",
        "latitude": 18.9388,
        "longitude": 72.8354,
        "severity": 8,
        "people_affected": 0,
        "injured": 0,
        "critical_injured": 0,
        "urgency": 5,
        "reported_time": "2026-09-16T10:40:00+05:30",
        "status": "CANCELLED",
    },
]



DEMO_RESOURCE_ECONOMICS: dict[str, tuple[float, float]] = {
    "AMBULANCE": (900.0, 20.0),
    "FIRE_ENGINE": (1800.0, 28.0),
    "RESCUE_TEAM": (1200.0, 22.0),
    "RESCUE_BOAT": (1400.0, 18.0),
    "MEDICAL_TEAM": (750.0, 15.0),
    "HELICOPTER": (5000.0, 35.0),
    "MEDICAL_KIT": (250.0, 8.0),
    "BLOOD_UNIT": (600.0, 12.0),
    "FOOD_SUPPLY": (80.0, 5.0),
    "WATER_SUPPLY": (40.0, 4.0),
    "SHELTER_KIT": (150.0, 6.0),
    "OTHER": (500.0, 25.0),
}


def _apply_demo_economics(connection: sqlite3.Connection) -> None:
    """Give demo resources transparent illustrative cost/risk values."""
    for resource_type, (cost, risk) in DEMO_RESOURCE_ECONOMICS.items():
        connection.execute(
            "UPDATE resources SET cost_per_unit = ?, risk_score = ? WHERE type = ? AND (cost_per_unit = 0 OR cost_per_unit IS NULL)",
            (cost, risk, resource_type),
        )


DEMO_RESOURCES = [
    {
        "name": "Rapid Response Ambulance Unit",
        "type": "AMBULANCE",
        "description": f"{DEMO_TAG} Emergency transport with advanced life support capability.",
        "quantity": 8,
        "available_quantity": 5,
        "latitude": 22.5726,
        "longitude": 88.3639,
        "location": "Central Medical Hub",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": 4,
    },
    {
        "name": "Urban Fire Engine Team",
        "type": "FIRE_ENGINE",
        "description": f"{DEMO_TAG} Engine crew equipped for structural and industrial fire response.",
        "quantity": 4,
        "available_quantity": 2,
        "latitude": 19.076,
        "longitude": 72.8777,
        "location": "Northpoint Fire Station",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": 12,
    },
    {
        "name": "Flood Rescue Boat Alpha",
        "type": "RESCUE_BOAT",
        "description": f"{DEMO_TAG} Flat-bottom rescue boat with trained water response crew.",
        "quantity": 3,
        "available_quantity": 3,
        "latitude": 22.5726,
        "longitude": 88.3639,
        "location": "East River Staging Area",
        "status": "AVAILABLE",
        "capacity": 10,
    },
    {
        "name": "Mobile Medical Team 04",
        "type": "MEDICAL_TEAM",
        "description": f"{DEMO_TAG} Clinicians and paramedics for triage and field treatment.",
        "quantity": 6,
        "available_quantity": 4,
        "latitude": 28.6139,
        "longitude": 77.209,
        "location": "Ring Road Medical Post",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": 10,
    },
    {
        "name": "Emergency Water Supply Pallets",
        "type": "WATER_SUPPLY",
        "description": f"{DEMO_TAG} Potable water units ready for shelter and evacuation support.",
        "quantity": 120,
        "available_quantity": 120,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "location": "South Distribution Depot",
        "status": "AVAILABLE",
        "capacity": None,
    },
    {
        "name": "Shelter Kit Reserve",
        "type": "SHELTER_KIT",
        "description": f"{DEMO_TAG} Weatherproof temporary shelter kits for displaced residents.",
        "quantity": 60,
        "available_quantity": 45,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "location": "South Distribution Depot",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": None,
    },
    {
        "name": "Rapid Urban Rescue Team",
        "type": "RESCUE_TEAM",
        "description": f"{DEMO_TAG} Rope and debris response crew for dense urban areas.",
        "quantity": 3,
        "available_quantity": 1,
        "latitude": 17.385,
        "longitude": 78.4867,
        "location": "Old Mill Response Base",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": 8,
    },
    {
        "name": "Coastal Lift Helicopter",
        "type": "HELICOPTER",
        "description": f"{DEMO_TAG} Airlift platform reserved for coastal evacuation support.",
        "quantity": 2,
        "available_quantity": 1,
        "latitude": 13.0827,
        "longitude": 80.2707,
        "location": "Coastline Air Station",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": 14,
    },
    {
        "name": "Trauma Medical Kit Crates",
        "type": "MEDICAL_KIT",
        "description": f"{DEMO_TAG} Field trauma kits for emergency triage posts.",
        "quantity": 40,
        "available_quantity": 18,
        "latitude": 28.6139,
        "longitude": 77.209,
        "location": "Ring Road Medical Post",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": None,
    },
    {
        "name": "Emergency Blood Unit Reserve",
        "type": "BLOOD_UNIT",
        "description": f"{DEMO_TAG} Refrigerated blood units staged for high-severity incidents.",
        "quantity": 80,
        "available_quantity": 27,
        "latitude": 19.076,
        "longitude": 72.8777,
        "location": "Northpoint Medical Store",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": None,
    },
    {
        "name": "Family Food Supply Boxes",
        "type": "FOOD_SUPPLY",
        "description": f"{DEMO_TAG} Shelf-stable food boxes for temporary evacuation shelters.",
        "quantity": 200,
        "available_quantity": 150,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "location": "South Distribution Depot",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": None,
    },
    {
        "name": "Mountain Rescue Team Bravo",
        "type": "RESCUE_TEAM",
        "description": f"{DEMO_TAG} High-angle rescue crew equipped for hillside access.",
        "quantity": 2,
        "available_quantity": 2,
        "latitude": 30.0668,
        "longitude": 79.0193,
        "location": "Western Ridge Outpost",
        "status": "AVAILABLE",
        "capacity": 6,
    },
    {
        "name": "Portable Fire Engine Unit",
        "type": "FIRE_ENGINE",
        "description": f"{DEMO_TAG} Compact engine currently held for maintenance inspection.",
        "quantity": 2,
        "available_quantity": 0,
        "latitude": 23.0225,
        "longitude": 72.5714,
        "location": "Meridian Works Fire Bay",
        "status": "MAINTENANCE",
        "capacity": 8,
    },
    {
        "name": "District Ambulance Reserve",
        "type": "AMBULANCE",
        "description": f"{DEMO_TAG} Secondary ambulance pool with limited dispatch availability.",
        "quantity": 5,
        "available_quantity": 2,
        "latitude": 23.0225,
        "longitude": 72.5714,
        "location": "Meridian District Clinic",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": 3,
    },
    {
        "name": "Flood Barrier Shelter Pack",
        "type": "SHELTER_KIT",
        "description": f"{DEMO_TAG} Portable shelter and barrier packs for flood displacement.",
        "quantity": 90,
        "available_quantity": 30,
        "latitude": 22.5726,
        "longitude": 88.3639,
        "location": "East River Staging Area",
        "status": "PARTIALLY_AVAILABLE",
        "capacity": None,
    },
]


def _insert_missing(
    connection: sqlite3.Connection,
    table: str,
    unique_field: str,
    records: list[dict[str, Any]],
) -> int:
    """Insert only new demo records, keeping restarts idempotent."""
    existing = {
        row[0]
        for row in connection.execute(
            f"SELECT {unique_field} FROM {table}"
        ).fetchall()
    }
    inserted = 0
    for record in records:
        if record[unique_field] in existing:
            continue
        columns = ", ".join(record)
        placeholders = ", ".join("?" for _ in record)
        connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(record.values()),
        )
        existing.add(record[unique_field])
        inserted += 1
    return inserted


def _label_existing_demo_records(connection: sqlite3.Connection) -> None:
    """Keep older Step 2 seed rows visibly marked as fictional demo data."""
    connection.execute(
        """
        UPDATE emergencies
        SET description = ? || ' ' || COALESCE(description, '')
        WHERE description NOT LIKE ? AND title IN (
            SELECT title FROM emergencies
        )
        """,
        (DEMO_TAG, f"{DEMO_TAG}%"),
    )
    connection.execute(
        """
        UPDATE resources
        SET description = ? || ' ' || COALESCE(description, '')
        WHERE description NOT LIKE ? AND name IN (
            SELECT name FROM resources
        )
        """,
        (DEMO_TAG, f"{DEMO_TAG}%"),
    )


def seed_demo_data(connection: sqlite3.Connection) -> None:
    """Ensure the database contains the complete fictional demo dataset."""
    _insert_missing(connection, "emergencies", "title", DEMO_EMERGENCIES)
    _insert_missing(connection, "resources", "name", DEMO_RESOURCES)
    _apply_demo_economics(connection)
    _label_existing_demo_records(connection)

    if connection.execute(
        "SELECT 1 FROM response_history LIMIT 1"
    ).fetchone() is None:
        first_emergency_id = connection.execute(
            "SELECT id FROM emergencies ORDER BY id LIMIT 1"
        ).fetchone()[0]
        first_resource_id = connection.execute(
            "SELECT id FROM resources ORDER BY id LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO response_history
                (emergency_id, resource_id, action, old_status, new_status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                first_emergency_id,
                first_resource_id,
                "DEMO_SEED",
                None,
                "ACTIVE",
                f"{DEMO_TAG} baseline record created for the Step 2 simulation.",
            ),
        )