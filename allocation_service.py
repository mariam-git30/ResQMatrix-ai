"""Persistence boundary for Step 4A allocation recommendations."""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping

from ai.optimizer import ResourceOptimizer


PRESERVED_ALLOCATION_STATUSES = {"APPROVED", "MODIFIED", "COMPLETED"}
RECOMMENDED_STATUS = "RECOMMENDED"


def _as_dict(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    return dict(row)


def replace_recommended_allocations(
    connection: sqlite3.Connection,
    recommendations: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Replace only RECOMMENDED rows and preserve completed operator decisions."""
    connection.execute(
        "DELETE FROM allocations WHERE status = ?",
        (RECOMMENDED_STATUS,),
    )
    inserted: list[dict[str, Any]] = []
    for recommendation in recommendations:
        cursor = connection.execute(
            """
            INSERT INTO allocations
                (emergency_id, resource_id, quantity, priority_score,
                 eta_minutes, allocation_reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recommendation["emergency_id"],
                recommendation["resource_id"],
                recommendation["quantity"],
                recommendation["priority_score"],
                recommendation["eta_minutes"],
                recommendation["allocation_reason"],
                RECOMMENDED_STATUS,
            ),
        )
        inserted.append(
            {
                **dict(recommendation),
                "allocation_id": cursor.lastrowid,
                "status": RECOMMENDED_STATUS,
            }
        )
    return inserted


def optimize_and_persist(
    connection: sqlite3.Connection,
    *,
    optimizer: ResourceOptimizer | None = None,
) -> dict[str, Any]:
    """Run the global optimizer and persist only fresh recommendations."""
    emergencies = [
        _as_dict(row)
        for row in connection.execute(
            "SELECT * FROM emergencies ORDER BY id"
        ).fetchall()
    ]
    resources = [
        _as_dict(row)
        for row in connection.execute(
            "SELECT * FROM resources ORDER BY id"
        ).fetchall()
    ]
    engine = optimizer or ResourceOptimizer()
    result = engine.optimize(emergencies, resources)
    recommendations = replace_recommended_allocations(
        connection,
        result["recommendations"],
    )
    return {
        "recommendations": recommendations,
        "fulfillment": result["fulfillment"],
        "unfulfilled_demand": result["unfulfilled_demand"],
        "weights": result["weights"],
    }


def list_allocations(
    connection: sqlite3.Connection,
    *,
    status: str | None = None,
    emergency_id: int | None = None,
) -> list[dict[str, Any]]:
    """List allocation records with optional operator-facing filters."""
    clauses: list[str] = []
    parameters: list[Any] = []
    if status:
        clauses.append("allocations.status = ?")
        parameters.append(status)
    if emergency_id is not None:
        clauses.append("allocations.emergency_id = ?")
        parameters.append(emergency_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""
        SELECT allocations.*, emergencies.title AS emergency_title,
               resources.name AS resource_name,
               resources.type AS resource_type
        FROM allocations
        LEFT JOIN emergencies ON emergencies.id = allocations.emergency_id
        LEFT JOIN resources ON resources.id = allocations.resource_id
        {where}
        ORDER BY allocations.created_at DESC, allocations.id DESC
        """,
        parameters,
    ).fetchall()
    return [_as_dict(row) for row in rows]
