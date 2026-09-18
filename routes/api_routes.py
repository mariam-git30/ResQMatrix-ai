"""REST-style APIs for emergencies, resources, and response history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from services.allocation_service import (
    list_allocations as list_allocations_service,
    optimize_and_persist,
)
from ai.priority_engine import PriorityEngine, rank_emergencies
from ai.optimizer import ResourceOptimizer
from database.db import connection_scope, get_connection, row_to_dict, rows_to_dicts


api_bp = Blueprint("api", __name__, url_prefix="/api")

EMERGENCY_TYPES = {
    "FIRE",
    "FLOOD",
    "ROAD_ACCIDENT",
    "BUILDING_COLLAPSE",
    "MEDICAL",
    "LANDSLIDE",
    "CYCLONE",
    "CHEMICAL",
    "OTHER",
}
EMERGENCY_STATUSES = {"ACTIVE", "IN_PROGRESS", "RESOLVED", "CANCELLED"}
RESOURCE_TYPES = {
    "AMBULANCE",
    "FIRE_ENGINE",
    "RESCUE_TEAM",
    "RESCUE_BOAT",
    "MEDICAL_TEAM",
    "HELICOPTER",
    "MEDICAL_KIT",
    "BLOOD_UNIT",
    "FOOD_SUPPLY",
    "WATER_SUPPLY",
    "SHELTER_KIT",
    "OTHER",
}
RESOURCE_STATUSES = {
    "AVAILABLE",
    "PARTIALLY_AVAILABLE",
    "DEPLOYED",
    "MAINTENANCE",
    "UNAVAILABLE",
}
ALLOCATION_STATUSES = {"RECOMMENDED", "APPROVED", "MODIFIED", "REJECTED", "COMPLETED"}


def _error(message: str, errors: dict[str, str] | None = None, status: int = 400):
    payload: dict[str, Any] = {"status": "error", "message": message}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), status


def _payload() -> dict[str, Any] | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _required_text(data: dict[str, Any], field: str, errors: dict[str, str]) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors[field] = "This field is required."
        return ""
    return value.strip()


def _text_or_none(data: dict[str, Any], field: str, errors: dict[str, str]) -> str | None:
    value = data.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        errors[field] = "Must be text."
        return None
    return value.strip()


def _number(
    data: dict[str, Any],
    field: str,
    errors: dict[str, str],
    *,
    default: int | float | None = None,
    integer: bool = False,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
) -> int | float | None:
    value = data.get(field, default)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        errors[field] = "Must be a number."
        return None
    try:
        parsed = int(value) if integer else float(value)
    except (TypeError, ValueError):
        errors[field] = "Must be a number."
        return None
    if integer and parsed != float(value):
        errors[field] = "Must be a whole number."
        return None
    if minimum is not None and parsed < minimum:
        errors[field] = f"Must be at least {minimum}."
    if maximum is not None and parsed > maximum:
        errors[field] = f"Must be at most {maximum}."
    return parsed


def _choice(
    data: dict[str, Any],
    field: str,
    choices: set[str],
    errors: dict[str, str],
    *,
    default: str | None = None,
) -> str:
    value = data.get(field, default)
    if not isinstance(value, str) or not value.strip():
        errors[field] = "This field is required."
        return ""
    normalized = value.strip().upper()
    if normalized not in choices:
        errors[field] = f"Must be one of: {', '.join(sorted(choices))}."
    return normalized


def _validate_emergency(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {
        "title": _required_text(data, "title", errors),
        "type": _choice(data, "type", EMERGENCY_TYPES, errors),
        "description": _text_or_none(data, "description", errors),
        "location": _required_text(data, "location", errors),
        "latitude": _number(data, "latitude", errors, minimum=-90, maximum=90),
        "longitude": _number(data, "longitude", errors, minimum=-180, maximum=180),
        "severity": _number(
            data, "severity", errors, default=0, integer=True, minimum=0, maximum=100
        ),
        "people_affected": _number(
            data, "people_affected", errors, default=0, integer=True, minimum=0
        ),
        "injured": _number(
            data, "injured", errors, default=0, integer=True, minimum=0
        ),
        "critical_injured": _number(
            data, "critical_injured", errors, default=0, integer=True, minimum=0
        ),
        "urgency": _number(
            data, "urgency", errors, default=0, integer=True, minimum=0, maximum=100
        ),
        "reported_time": _text_or_none(data, "reported_time", errors),
        "status": _choice(
            data, "status", EMERGENCY_STATUSES, errors, default="ACTIVE"
        ),
    }
    if (
        cleaned["critical_injured"] is not None
        and cleaned["injured"] is not None
        and cleaned["critical_injured"] > cleaned["injured"]
    ):
        errors["critical_injured"] = "Cannot exceed injured."
    if (
        cleaned["injured"] is not None
        and cleaned["people_affected"] is not None
        and cleaned["injured"] > cleaned["people_affected"]
    ):
        errors["injured"] = "Cannot exceed people affected."
    return cleaned, errors


def _validate_resource(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {
        "name": _required_text(data, "name", errors),
        "type": _choice(data, "type", RESOURCE_TYPES, errors),
        "description": _text_or_none(data, "description", errors),
        "quantity": _number(
            data, "quantity", errors, default=0, integer=True, minimum=0
        ),
        "available_quantity": _number(
            data, "available_quantity", errors, default=0, integer=True, minimum=0
        ),
        "latitude": _number(data, "latitude", errors, minimum=-90, maximum=90),
        "longitude": _number(data, "longitude", errors, minimum=-180, maximum=180),
        "location": _required_text(data, "location", errors),
        "status": _choice(
            data, "status", RESOURCE_STATUSES, errors, default="AVAILABLE"
        ),
        "capacity": _number(
            data, "capacity", errors, integer=True, minimum=0
        ),
        "cost_per_unit": _number(
            data, "cost_per_unit", errors, default=0, minimum=0
        ),
        "risk_score": _number(
            data, "risk_score", errors, default=50, minimum=0, maximum=100
        ),
    }
    if (
        cleaned["available_quantity"] is not None
        and cleaned["quantity"] is not None
        and cleaned["available_quantity"] > cleaned["quantity"]
    ):
        errors["available_quantity"] = "Cannot exceed quantity."
    return cleaned, errors


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_history(
    connection: sqlite3.Connection,
    *,
    emergency_id: int | None = None,
    resource_id: int | None = None,
    action: str,
    old_status: str | None = None,
    new_status: str | None = None,
    notes: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO response_history
            (emergency_id, resource_id, action, old_status, new_status, notes, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            emergency_id,
            resource_id,
            action,
            old_status,
            new_status,
            notes,
            _now(),
        ),
    )


def _merged_payload(existing: sqlite3.Row, data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(data)
    return merged


@api_bp.get("/dashboard/stats")
def dashboard_stats():
    """Return live totals used by the operator dashboard."""
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        stats = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM emergencies
                 WHERE status IN ('ACTIVE', 'IN_PROGRESS')) AS active_incidents,
                (SELECT COALESCE(SUM(available_quantity), 0) FROM resources
                 WHERE status IN ('AVAILABLE', 'PARTIALLY_AVAILABLE')) AS available_resources,
                (SELECT COUNT(*) FROM response_history
                 WHERE date(timestamp) = date('now')) AS response_actions_today,
                (SELECT COUNT(*) FROM emergencies) AS total_emergencies,
                (SELECT COUNT(*) FROM resources) AS total_resources
            """
        ).fetchone()
        return jsonify({"status": "success", "data": row_to_dict(stats)})
    finally:
        connection.close()


@api_bp.get("/emergencies")
def list_emergencies():
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        rows = connection.execute(
            "SELECT * FROM emergencies ORDER BY urgency DESC, created_at DESC"
        ).fetchall()
        return jsonify({"status": "success", "data": rows_to_dicts(rows)})
    finally:
        connection.close()


@api_bp.post("/emergencies")
def create_emergency():
    data = _payload()
    if data is None:
        return _error("Request body must be a JSON object.")
    cleaned, errors = _validate_emergency(data)
    if errors:
        return _error("Emergency validation failed.", errors)
    fields = list(cleaned)
    placeholders = ", ".join("?" for _ in fields)
    with connection_scope(current_app.config["DATABASE_PATH"]) as connection:
        cursor = connection.execute(
            f"INSERT INTO emergencies ({', '.join(fields)}) VALUES ({placeholders})",
            tuple(cleaned[field] for field in fields),
        )
        emergency_id = cursor.lastrowid
        _record_history(
            connection,
            emergency_id=emergency_id,
            action="CREATED",
            new_status=cleaned["status"],
            notes="Emergency created by operator.",
        )
        row = connection.execute(
            "SELECT * FROM emergencies WHERE id = ?", (emergency_id,)
        ).fetchone()
    return jsonify({"status": "success", "data": row_to_dict(row)}), 201


@api_bp.route("/emergencies/<int:emergency_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
def emergency_detail(emergency_id: int):
    database_path = current_app.config["DATABASE_PATH"]
    if request.method == "GET":
        connection = get_connection(database_path)
        try:
            row = connection.execute(
                "SELECT * FROM emergencies WHERE id = ?", (emergency_id,)
            ).fetchone()
            if row is None:
                return _error("Emergency not found.", status=404)
            return jsonify({"status": "success", "data": row_to_dict(row)})
        finally:
            connection.close()

    with connection_scope(database_path) as connection:
        existing = connection.execute(
            "SELECT * FROM emergencies WHERE id = ?", (emergency_id,)
        ).fetchone()
        if existing is None:
            return _error("Emergency not found.", status=404)
        if request.method == "DELETE":
            _record_history(
                connection,
                emergency_id=emergency_id,
                action="DELETED",
                old_status=existing["status"],
                notes="Emergency removed by operator.",
            )
            connection.execute("DELETE FROM emergencies WHERE id = ?", (emergency_id,))
            return jsonify({"status": "success", "message": "Emergency deleted."})

        data = _payload()
        if data is None:
            return _error("Request body must be a JSON object.")
        cleaned, errors = _validate_emergency(_merged_payload(existing, data))
        if errors:
            return _error("Emergency validation failed.", errors)
        fields = list(cleaned)
        connection.execute(
            f"UPDATE emergencies SET {', '.join(f'{field} = ?' for field in fields)} WHERE id = ?",
            tuple(cleaned[field] for field in fields) + (emergency_id,),
        )
        _record_history(
            connection,
            emergency_id=emergency_id,
            action="UPDATED",
            old_status=existing["status"],
            new_status=cleaned["status"],
            notes="Emergency details updated by operator.",
        )
        row = connection.execute(
            "SELECT * FROM emergencies WHERE id = ?", (emergency_id,)
        ).fetchone()
    return jsonify({"status": "success", "data": row_to_dict(row)})


@api_bp.get("/resources")
def list_resources():
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        rows = connection.execute(
            "SELECT * FROM resources ORDER BY status, name"
        ).fetchall()
        return jsonify({"status": "success", "data": rows_to_dicts(rows)})
    finally:
        connection.close()


@api_bp.post("/resources")
def create_resource():
    data = _payload()
    if data is None:
        return _error("Request body must be a JSON object.")
    cleaned, errors = _validate_resource(data)
    if errors:
        return _error("Resource validation failed.", errors)
    fields = list(cleaned)
    placeholders = ", ".join("?" for _ in fields)
    with connection_scope(current_app.config["DATABASE_PATH"]) as connection:
        cursor = connection.execute(
            f"INSERT INTO resources ({', '.join(fields)}) VALUES ({placeholders})",
            tuple(cleaned[field] for field in fields),
        )
        resource_id = cursor.lastrowid
        _record_history(
            connection,
            resource_id=resource_id,
            action="CREATED",
            new_status=cleaned["status"],
            notes="Resource created by operator.",
        )
        row = connection.execute(
            "SELECT * FROM resources WHERE id = ?", (resource_id,)
        ).fetchone()
    return jsonify({"status": "success", "data": row_to_dict(row)}), 201


@api_bp.route("/resources/<int:resource_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
def resource_detail(resource_id: int):
    database_path = current_app.config["DATABASE_PATH"]
    if request.method == "GET":
        connection = get_connection(database_path)
        try:
            row = connection.execute(
                "SELECT * FROM resources WHERE id = ?", (resource_id,)
            ).fetchone()
            if row is None:
                return _error("Resource not found.", status=404)
            return jsonify({"status": "success", "data": row_to_dict(row)})
        finally:
            connection.close()

    with connection_scope(database_path) as connection:
        existing = connection.execute(
            "SELECT * FROM resources WHERE id = ?", (resource_id,)
        ).fetchone()
        if existing is None:
            return _error("Resource not found.", status=404)
        if request.method == "DELETE":
            _record_history(
                connection,
                resource_id=resource_id,
                action="DELETED",
                old_status=existing["status"],
                notes="Resource removed by operator.",
            )
            connection.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
            return jsonify({"status": "success", "message": "Resource deleted."})

        data = _payload()
        if data is None:
            return _error("Request body must be a JSON object.")
        cleaned, errors = _validate_resource(_merged_payload(existing, data))
        if errors:
            return _error("Resource validation failed.", errors)
        fields = list(cleaned)
        connection.execute(
            f"UPDATE resources SET {', '.join(f'{field} = ?' for field in fields)} WHERE id = ?",
            tuple(cleaned[field] for field in fields) + (resource_id,),
        )
        _record_history(
            connection,
            resource_id=resource_id,
            action="UPDATED",
            old_status=existing["status"],
            new_status=cleaned["status"],
            notes="Resource details updated by operator.",
        )
        row = connection.execute(
            "SELECT * FROM resources WHERE id = ?", (resource_id,)
        ).fetchone()
    return jsonify({"status": "success", "data": row_to_dict(row)})


def _priority_context(
    connection: sqlite3.Connection,
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """Read the current emergency and resource data for a side-effect-free score."""
    emergencies = connection.execute(
        "SELECT * FROM emergencies ORDER BY id"
    ).fetchall()
    resources = connection.execute(
        "SELECT * FROM resources ORDER BY id"
    ).fetchall()
    return emergencies, resources


@api_bp.post("/priority/calculate")
def calculate_priority():
    """Calculate one emergency's current local priority score."""
    data = _payload()
    if data is None:
        return _error("Request body must be a JSON object.")
    emergency_id = data.get("emergency_id")
    if isinstance(emergency_id, bool) or not isinstance(emergency_id, int):
        return _error("emergency_id must be an integer.")
    if emergency_id <= 0:
        return _error("emergency_id must be a positive integer.")

    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        emergency = connection.execute(
            "SELECT * FROM emergencies WHERE id = ?", (emergency_id,)
        ).fetchone()
        if emergency is None:
            return _error("Emergency not found.", status=404)
        emergencies, resources = _priority_context(connection)
        result = PriorityEngine().calculate(emergency, emergencies, resources)
        return jsonify({"status": "success", "data": result})
    finally:
        connection.close()


@api_bp.get("/priority/emergencies")
def list_priority_emergencies():
    """Return active emergencies ranked by the local prototype engine."""
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        emergencies, resources = _priority_context(connection)
        active = [
            emergency
            for emergency in emergencies
            if emergency["status"] in {"ACTIVE", "IN_PROGRESS"}
        ]
        ranked = rank_emergencies(active, resources)
        return jsonify({"status": "success", "data": ranked})
    finally:
        connection.close()


@api_bp.get("/allocations")
def list_allocations():
    """Expose recommendations and operator decisions with optional filters."""
    status = request.args.get("status")
    if status:
        status = status.strip().upper()
        if status not in ALLOCATION_STATUSES:
            return _error(
                f"status must be one of: {', '.join(sorted(ALLOCATION_STATUSES))}."
            )
    emergency_id_value = request.args.get("emergency_id")
    emergency_id: int | None = None
    if emergency_id_value is not None:
        try:
            emergency_id = int(emergency_id_value)
        except (TypeError, ValueError):
            return _error("emergency_id must be an integer.")
        if emergency_id <= 0:
            return _error("emergency_id must be a positive integer.")
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        rows = list_allocations_service(
            connection,
            status=status,
            emergency_id=emergency_id,
        )
        return jsonify({"status": "success", "data": rows})
    finally:
        connection.close()



@api_bp.post("/optimize")
def optimize_allocations():
    """Run the global optimizer with optional operator-defined constraints."""
    data = _payload() or {}
    config: dict[str, Any] = {}
    for field in ("max_distance_km", "max_eta_minutes", "cost_reference", "min_reserve_quantity"):
        if field in data:
            value = data[field]
            try:
                parsed = int(value) if field == "min_reserve_quantity" else float(value)
            except (TypeError, ValueError):
                return _error(f"{field} must be a number.")
            if parsed < 0 or (field in {"max_distance_km", "max_eta_minutes", "cost_reference"} and parsed == 0):
                return _error(f"{field} must be greater than zero.")
            config[field] = parsed
    if isinstance(data.get("weights"), dict):
        config["weights"] = {key: value for key, value in data["weights"].items() if key in {
            "priority", "compatibility", "proximity", "eta", "availability", "scarcity", "fairness", "cost", "risk"
        }}
    try:
        with connection_scope(current_app.config["DATABASE_PATH"]) as connection:
            result = optimize_and_persist(connection, optimizer=ResourceOptimizer(config))
        result["constraints"] = {
            "max_distance_km": config.get("max_distance_km", 750.0),
            "max_eta_minutes": config.get("max_eta_minutes", 720.0),
            "cost_reference": config.get("cost_reference", 5000.0),
            "min_reserve_quantity": config.get("min_reserve_quantity", 0),
        }
        return jsonify({"status": "success", "data": result})
    except Exception as exc:
        current_app.logger.exception("Optimization failed")
        return _error(f"Optimization failed: {exc}", status=500)


@api_bp.post("/allocations/<int:allocation_id>/approve")
def approve_allocation(allocation_id: int):
    """Approve a recommendation and reconcile the resource quantity atomically."""
    with connection_scope(current_app.config["DATABASE_PATH"]) as connection:
        allocation = connection.execute(
            "SELECT * FROM allocations WHERE id = ?", (allocation_id,)
        ).fetchone()
        if allocation is None:
            return _error("Allocation not found.", status=404)
        if allocation["status"] not in {"RECOMMENDED", "MODIFIED"}:
            return _error("Only recommended or modified allocations can be approved.")
        resource = connection.execute(
            "SELECT * FROM resources WHERE id = ?", (allocation["resource_id"],)
        ).fetchone()
        if resource is None:
            return _error("Resource not found.", status=404)
        qty = int(allocation["quantity"] or 0)
        available = int(resource["available_quantity"] or 0)
        if qty <= 0:
            return _error("Allocation quantity must be positive.")
        if qty > available:
            return _error(
                f"This recommendation is no longer feasible: {qty} unit(s) were recommended, but only {available} unit(s) are currently available. Resource availability changed; run optimization again before approving.",
                status=409,
            )
        remaining = available - qty
        new_resource_status = "DEPLOYED" if remaining == 0 else "PARTIALLY_AVAILABLE"
        connection.execute(
            "UPDATE resources SET available_quantity = ?, status = ? WHERE id = ?",
            (remaining, new_resource_status, resource["id"]),
        )
        connection.execute(
            "UPDATE allocations SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (allocation_id,),
        )
        _record_history(
            connection,
            emergency_id=allocation["emergency_id"],
            resource_id=allocation["resource_id"],
            action="ALLOCATION_APPROVED",
            old_status=allocation["status"],
            new_status="APPROVED",
            notes=f"Operator approved {qty} unit(s); remaining resource quantity: {remaining}.",
        )
        updated = connection.execute(
            "SELECT * FROM allocations WHERE id = ?", (allocation_id,)
        ).fetchone()
    return jsonify({"status": "success", "data": row_to_dict(updated)})


@api_bp.post("/allocations/<int:allocation_id>/reject")
def reject_allocation(allocation_id: int):
    """Reject a recommendation without changing resource quantities."""
    with connection_scope(current_app.config["DATABASE_PATH"]) as connection:
        allocation = connection.execute(
            "SELECT * FROM allocations WHERE id = ?", (allocation_id,)
        ).fetchone()
        if allocation is None:
            return _error("Allocation not found.", status=404)
        if allocation["status"] not in {"RECOMMENDED", "MODIFIED"}:
            return _error("Only recommended or modified allocations can be rejected.")
        connection.execute(
            "UPDATE allocations SET status = 'REJECTED' WHERE id = ?", (allocation_id,)
        )
        _record_history(
            connection,
            emergency_id=allocation["emergency_id"],
            resource_id=allocation["resource_id"],
            action="ALLOCATION_REJECTED",
            old_status=allocation["status"],
            new_status="REJECTED",
            notes="Operator rejected the AI recommendation; no resource quantity changed.",
        )
        updated = connection.execute(
            "SELECT * FROM allocations WHERE id = ?", (allocation_id,)
        ).fetchone()
    return jsonify({"status": "success", "data": row_to_dict(updated)})


@api_bp.post("/simulation/run")
def run_simulation():
    """Run a non-persistent what-if scenario against a copied in-memory dataset."""
    data = _payload() or {}
    resource_reduction = data.get("resource_reduction_percent", 0)
    try:
        reduction = max(0.0, min(100.0, float(resource_reduction)))
    except (TypeError, ValueError):
        return _error("resource_reduction_percent must be a number from 0 to 100.")
    with get_connection(current_app.config["DATABASE_PATH"]) as connection:
        emergencies = rows_to_dicts(connection.execute("SELECT * FROM emergencies ORDER BY id").fetchall())
        resources = rows_to_dicts(connection.execute("SELECT * FROM resources ORDER BY id").fetchall())
        from ai.optimizer import ResourceOptimizer
        baseline = ResourceOptimizer().optimize(emergencies, resources)
        scenario_resources = []
        for resource in resources:
            copied = dict(resource)
            copied["available_quantity"] = int((int(resource.get("available_quantity") or 0) * (100.0 - reduction)) // 100)
            if copied["available_quantity"] == 0 and copied.get("status") in {"AVAILABLE", "PARTIALLY_AVAILABLE", "DEPLOYED"}:
                copied["status"] = "UNAVAILABLE"
            scenario_resources.append(copied)
        scenario = ResourceOptimizer().optimize(emergencies, scenario_resources)
    return jsonify({
        "status": "success",
        "data": {
            "scenario": {"resource_reduction_percent": reduction},
            "baseline": {
                "recommendation_count": len(baseline["recommendations"]),
                "unfulfilled_count": len(baseline["unfulfilled_demand"]),
            },
            "what_if": {
                "recommendation_count": len(scenario["recommendations"]),
                "unfulfilled_count": len(scenario["unfulfilled_demand"]),
                "unfulfilled_demand": scenario["unfulfilled_demand"],
            },
        },
    })


@api_bp.get("/analytics")
def analytics():
    """Return lightweight decision-support analytics from SQLite history."""
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        active = connection.execute("SELECT COUNT(*) FROM emergencies WHERE status IN ('ACTIVE','IN_PROGRESS')").fetchone()[0]
        resolved = connection.execute("SELECT COUNT(*) FROM emergencies WHERE status = 'RESOLVED'").fetchone()[0]
        approved = connection.execute("SELECT COUNT(*) FROM allocations WHERE status = 'APPROVED'").fetchone()[0]
        recommended = connection.execute("SELECT COUNT(*) FROM allocations WHERE status = 'RECOMMENDED'").fetchone()[0]
        rejected = connection.execute("SELECT COUNT(*) FROM allocations WHERE status = 'REJECTED'").fetchone()[0]
        by_type = [dict(row) for row in connection.execute(
            "SELECT type, COUNT(*) AS count FROM emergencies GROUP BY type ORDER BY count DESC"
        ).fetchall()]
        by_status = [dict(row) for row in connection.execute(
            "SELECT status, COUNT(*) AS count FROM allocations GROUP BY status ORDER BY count DESC"
        ).fetchall()]
        actions = [dict(row) for row in connection.execute(
            "SELECT action, COUNT(*) AS count FROM response_history GROUP BY action ORDER BY count DESC LIMIT 10"
        ).fetchall()]
        return jsonify({"status":"success","data":{
            "emergencies":{"active":active,"resolved":resolved,"total":active+resolved+connection.execute("SELECT COUNT(*) FROM emergencies WHERE status NOT IN ('ACTIVE','IN_PROGRESS','RESOLVED')").fetchone()[0]},
            "allocations":{"approved":approved,"recommended":recommended,"rejected":rejected},
            "emergencies_by_type":by_type,"allocation_status":by_status,"actions":actions,
        }})
    finally:
        connection.close()

@api_bp.get("/history")
def list_history():
    emergency_id = request.args.get("emergency_id", type=int)
    resource_id = request.args.get("resource_id", type=int)
    clauses: list[str] = []
    parameters: list[int] = []
    if emergency_id is not None:
        clauses.append("response_history.emergency_id = ?")
        parameters.append(emergency_id)
    if resource_id is not None:
        clauses.append("response_history.resource_id = ?")
        parameters.append(resource_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    connection = get_connection(current_app.config["DATABASE_PATH"])
    try:
        rows = connection.execute(
            f"""
            SELECT response_history.*, emergencies.title AS emergency_title,
                   resources.name AS resource_name
            FROM response_history
            LEFT JOIN emergencies ON emergencies.id = response_history.emergency_id
            LEFT JOIN resources ON resources.id = response_history.resource_id
            {where}
            ORDER BY response_history.timestamp DESC
            LIMIT 50
            """,
            parameters,
        ).fetchall()
        return jsonify({"status": "success", "data": rows_to_dicts(rows)})
    finally:
        connection.close()