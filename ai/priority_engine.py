"""Configurable, local emergency priority scoring.

This module intentionally contains a transparent decision-support prototype.
It does not allocate, dispatch, or modify emergency or resource records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


# Keep the prototype's weights and thresholds together so operators can
# review or tune the policy without changing the scoring implementation.
DEFAULT_PRIORITY_CONFIG: dict[str, Any] = {
    "weights": {
        "severity": 0.25,
        "critical_injuries": 0.25,
        "people_affected": 0.15,
        "urgency": 0.15,
        "injured": 0.10,
        "time_elapsed": 0.05,
        "resource_scarcity": 0.05,
    },
    "thresholds": {
        "low_max": 24.99,
        "medium_max": 49.99,
        "high_max": 74.99,
    },
    "max_elapsed_hours": 24.0,
}

RESOURCE_COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "FIRE": ("FIRE_ENGINE", "RESCUE_TEAM"),
    "FLOOD": ("RESCUE_BOAT", "RESCUE_TEAM", "AMBULANCE"),
    "ROAD_ACCIDENT": ("AMBULANCE", "MEDICAL_TEAM", "RESCUE_TEAM"),
    "BUILDING_COLLAPSE": ("RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM"),
    "MEDICAL": ("AMBULANCE", "MEDICAL_TEAM", "MEDICAL_KIT"),
    "LANDSLIDE": ("RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM"),
    "CYCLONE": ("RESCUE_TEAM", "AMBULANCE", "RESCUE_BOAT", "MEDICAL_TEAM"),
    "CHEMICAL": ("RESCUE_TEAM", "AMBULANCE", "MEDICAL_TEAM"),
}

FACTOR_LABELS = {
    "severity": "Severity",
    "critical_injuries": "Critical injuries",
    "people_affected": "People affected",
    "urgency": "Urgency",
    "injured": "Injured",
    "time_elapsed": "Time elapsed",
    "resource_scarcity": "Resource scarcity",
}


def _number(value: Any, default: float = 0.0) -> float:
    """Read a finite non-negative number without allowing bad input to leak."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _mapping_value(record: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read from dictionaries and sqlite3.Row-like mappings alike."""
    try:
        return record[key]
    except (KeyError, IndexError, TypeError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _copy_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "weights": dict(DEFAULT_PRIORITY_CONFIG["weights"]),
        "thresholds": dict(DEFAULT_PRIORITY_CONFIG["thresholds"]),
        "max_elapsed_hours": DEFAULT_PRIORITY_CONFIG["max_elapsed_hours"],
    }
    if config:
        if isinstance(config.get("weights"), Mapping):
            merged["weights"].update(config["weights"])
        if isinstance(config.get("thresholds"), Mapping):
            merged["thresholds"].update(config["thresholds"])
        if "max_elapsed_hours" in config:
            merged["max_elapsed_hours"] = config["max_elapsed_hours"]
    return merged


class PriorityEngine:
    """Calculate explainable priority scores without side effects."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = _copy_config(config)
        self.weights = {
            factor: _number(weight)
            for factor, weight in self.config["weights"].items()
        }
        self.thresholds = {
            name: _number(value)
            for name, value in self.config["thresholds"].items()
        }
        self.max_elapsed_hours = max(
            _number(self.config.get("max_elapsed_hours"), 24.0),
            0.01,
        )

    def calculate(
        self,
        emergency: Mapping[str, Any],
        emergencies: Iterable[Mapping[str, Any]] | None = None,
        resources: Iterable[Mapping[str, Any]] | None = None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return a score and its evidence for one emergency.

        ``emergencies`` is the current dataset used for relative population
        and injury normalization. ``resources`` is read only for scarcity.
        """
        dataset = list(emergencies) if emergencies is not None else [emergency]
        resource_list = list(resources or [])
        max_people = max(
            (_number(_mapping_value(item, "people_affected")) for item in dataset),
            default=0.0,
        )
        max_injured = max(
            (_number(_mapping_value(item, "injured")) for item in dataset),
            default=0.0,
        )
        max_critical = max(
            (_number(_mapping_value(item, "critical_injured")) for item in dataset),
            default=0.0,
        )

        factors = {
            "severity": _clamp(_number(_mapping_value(emergency, "severity"))),
            "critical_injuries": self._relative_factor(
                _number(_mapping_value(emergency, "critical_injured")),
                max_critical,
            ),
            "people_affected": self._relative_factor(
                _number(_mapping_value(emergency, "people_affected")),
                max_people,
            ),
            "urgency": _clamp(_number(_mapping_value(emergency, "urgency"))),
            "injured": self._relative_factor(
                _number(_mapping_value(emergency, "injured")),
                max_injured,
            ),
            "time_elapsed": self.time_elapsed_factor(
                _mapping_value(emergency, "reported_time"),
                now=now,
            ),
            "resource_scarcity": self.resource_scarcity(
                _mapping_value(emergency, "type"),
                resource_list,
            ),
        }
        weighted_contributions = {
            factor: factors[factor] * self.weights.get(factor, 0.0)
            for factor in factors
        }
        score = _clamp(sum(weighted_contributions.values()))
        score = round(score, 2)
        top_factors = [
            {
                "factor": factor,
                "label": FACTOR_LABELS[factor],
                "score": round(factors[factor], 2),
                "weighted_contribution": round(weighted_contributions[factor], 2),
            }
            for factor in sorted(
                factors,
                key=lambda name: weighted_contributions[name],
                reverse=True,
            )[:3]
        ]
        return {
            "emergency_id": _mapping_value(emergency, "id"),
            "priority_score": score,
            "priority_level": self.priority_level(score),
            "factors": {key: round(value, 2) for key, value in factors.items()},
            "weights": dict(self.weights),
            "top_factors": top_factors,
            "explanation": self.explain(
                emergency,
                factors,
                top_factors,
                score,
            ),
        }

    @staticmethod
    def _relative_factor(value: float, maximum: float) -> float:
        if maximum <= 0:
            return 0.0
        return _clamp((value / maximum) * 100)

    def time_elapsed_factor(
        self,
        reported_time: Any,
        *,
        now: datetime | None = None,
    ) -> float:
        parsed = _parse_datetime(reported_time)
        if parsed is None:
            return 0.0
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        elapsed_hours = max(
            (current.astimezone(timezone.utc) - parsed).total_seconds() / 3600,
            0.0,
        )
        return _clamp((elapsed_hours / self.max_elapsed_hours) * 100)

    @staticmethod
    def resource_scarcity(
        emergency_type: Any,
        resources: Sequence[Mapping[str, Any]],
    ) -> float:
        compatible_types = RESOURCE_COMPATIBILITY.get(str(emergency_type or "").upper())
        if not compatible_types:
            return 0.0
        matching = [
            resource
            for resource in resources
            if str(_mapping_value(resource, "type", "")).upper() in compatible_types
        ]
        if not matching:
            return 100.0
        total_quantity = sum(
            _number(_mapping_value(resource, "quantity")) for resource in matching
        )
        available_quantity = sum(
            _number(_mapping_value(resource, "available_quantity"))
            for resource in matching
            if str(_mapping_value(resource, "status", "")).upper()
            in {"AVAILABLE", "PARTIALLY_AVAILABLE"}
        )
        if total_quantity <= 0:
            return 100.0
        return _clamp(100 - ((available_quantity / total_quantity) * 100))

    def priority_level(self, score: float) -> str:
        if score <= self.thresholds["low_max"]:
            return "LOW"
        if score <= self.thresholds["medium_max"]:
            return "MEDIUM"
        if score <= self.thresholds["high_max"]:
            return "HIGH"
        return "CRITICAL"

    def explain(
        self,
        emergency: Mapping[str, Any],
        factors: Mapping[str, float],
        top_factors: Sequence[Mapping[str, Any]],
        score: float,
    ) -> str:
        level = self.priority_level(score)
        if top_factors:
            lead = ", ".join(
                f"{item['label']} ({item['score']:.0f}/100)"
                for item in top_factors
            )
        else:
            lead = "no measurable factors"
        missing_time = _parse_datetime(_mapping_value(emergency, "reported_time")) is None
        time_note = (
            " Reported time was missing or invalid, so elapsed time contributed 0."
            if missing_time
            else ""
        )
        scarcity_note = (
            " Compatible resources are scarce."
            if factors["resource_scarcity"] >= 60
            else " Compatible resource availability is not a major scarcity signal."
        )
        return (
            f"This {level.lower()} priority is {score:.2f}/100. "
            f"The strongest factor signals are {lead}.{scarcity_note}{time_note} "
            "The score is a configurable rule-based decision-support signal "
            "for human operator review."
        )


def rank_emergencies(
    emergencies: Iterable[Mapping[str, Any]],
    resources: Iterable[Mapping[str, Any]] | None = None,
    *,
    engine: PriorityEngine | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Calculate and sort a collection by descending prototype score."""
    dataset = list(emergencies)
    scorer = engine or PriorityEngine()
    ranked = [
        scorer.calculate(item, dataset, resources, now=now)
        for item in dataset
    ]
    return sorted(
        ranked,
        key=lambda result: result["priority_score"],
        reverse=True,
    )